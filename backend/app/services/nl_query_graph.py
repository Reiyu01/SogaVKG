import json
import os
from typing import Any, TypedDict

from openai import OpenAI
from langgraph.graph import END, START, StateGraph

from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper
from app.semantic.query_builder import SemanticQueryBuilder
from app.semantic.schema_description import build_schema_description
from app.services.query_service import QueryService


MAX_RETRIES = 2


QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "build_semantic_query",
        "description": (
            "當使用者想要查詢資產資料庫的內容時，呼叫這個工具組出查詢。"
            "只能使用 schema 說明中列出的 entity 和欄位名稱，不可以自己發明。"
            "如果使用者只是打招呼、閒聊、或問跟查詢無關的問題，不要呼叫這個工具，"
            "直接用文字自然回答就好。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "operator": {
                                "type": "string",
                                "enum": [
                                    "=", "!=", ">", ">=",
                                    "<", "<=", "LIKE", "IN",
                                ],
                            },
                            "value": {},
                        },
                        "required": ["field", "operator", "value"],
                    },
                },
                "order_by": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "direction": {
                            "type": "string",
                            "enum": ["ASC", "DESC"],
                        },
                    },
                },
                "limit": {"type": "integer"},
            },
            "required": ["entity"],
        },
    },
}


class GraphState(TypedDict, total=False):
    question: str
    raw_query: dict[str, Any] | None
    semantic_query: SemanticQuery
    chat_reply: str | None
    error: str | None
    attempts: int
    result: dict[str, Any]


class NLQueryGraph:
    """
    用 LangGraph 包裝「自然語言 -> 聊天回覆 或 SemanticQuery -> 執行查詢」的流程。
    模型可以自由選擇要不要呼叫查詢工具：
      - 使用者在聊天 -> 模型直接用文字回答，不查資料庫
      - 使用者想查資料 -> 模型呼叫工具，走原本的驗證/執行/重試流程
    """

    def __init__(self, mapper: SemanticMapper, query_service: QueryService):
        self.mapper = mapper
        self.query_service = query_service
        self.builder = SemanticQueryBuilder(mapper)

        self.client = OpenAI(
            base_url=os.environ["MY_MODEL_BASE_URL"],
            api_key=os.environ.get("MY_MODEL_API_KEY", "not-needed"),
        )
        self.model_name = os.environ["MY_MODEL_NAME"]

        self.schema_text = build_schema_description(mapper)
        self.graph = self._build_graph()

    # ------------------------------------------------------
    # Graph 組裝
    # ------------------------------------------------------

    def _build_graph(self):
        workflow = StateGraph(GraphState)

        workflow.add_node("translate", self._translate_node)
        workflow.add_node("validate", self._validate_node)
        workflow.add_node("execute", self._execute_node)

        workflow.add_edge(START, "translate")

        workflow.add_conditional_edges(
            "translate",
            self._route_after_translate,
            {
                "chat": END,
                "validate": "validate",
            },
        )

        workflow.add_conditional_edges(
            "validate",
            self._route_after_validate,
            {
                "retry": "translate",
                "execute": "execute",
                "give_up": END,
            },
        )

        workflow.add_edge("execute", END)

        return workflow.compile()

    # ------------------------------------------------------
    # Node：翻譯 / 聊天
    # ------------------------------------------------------

    def _translate_node(self, state: GraphState) -> dict:
        system_prompt = (
            "你是一個資產查詢助手，同時也可以進行一般對話。\n\n"
            f"目前系統可查詢的 entity 與欄位：\n\n{self.schema_text}\n"
            "規則：\n"
            "1. 如果使用者的問題是想查詢資產資料庫的內容（例如問有哪些資產、"
            "數量、地點、類別等），呼叫 build_semantic_query 工具。\n"
            "2. entity 和欄位名稱只能使用上面列出的名稱，不可以自己發明。\n"
            "3. 模糊比對用 LIKE。\n"
            "4. 如果使用者只是打招呼、閒聊、問你是誰、或問跟查詢無關的一般問題，"
            "直接用自然的文字回答，不要呼叫工具。"
        )

        user_content = state["question"]

        if state.get("error"):
            user_content += (
                f"\n\n（上一次你的回答有問題：{state['error']}，"
                f"請根據可用的欄位重新修正。）"
            )

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            tools=[QUERY_TOOL],
            tool_choice="auto",
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls

        attempts = state.get("attempts", 0) + 1

        # 模型選擇不呼叫工具 -> 純聊天回覆
        if not tool_calls:
            return {
                "chat_reply": message.content or "（沒有回覆內容）",
                "raw_query": None,
                "error": None,
                "attempts": attempts,
            }

        try:
            raw_query = json.loads(tool_calls[0].function.arguments)
        except json.JSONDecodeError:
            return {
                "raw_query": None,
                "chat_reply": None,
                "error": "模型回傳的參數不是合法 JSON",
                "attempts": attempts,
            }

        return {
            "raw_query": raw_query,
            "chat_reply": None,
            "attempts": attempts,
        }

    def _route_after_translate(self, state: GraphState) -> str:
        if state.get("chat_reply") is not None:
            return "chat"
        return "validate"

    # ------------------------------------------------------
    # Node：驗證
    # ------------------------------------------------------

    def _validate_node(self, state: GraphState) -> dict:
        raw_query = state.get("raw_query")

        if raw_query is None:
            return {"error": state.get("error", "翻譯失敗")}

        try:
            semantic_query = SemanticQuery(**raw_query)
        except Exception as exc:
            return {"error": f"查詢格式不正確：{exc}"}

        try:
            self.builder.build(semantic_query)
        except ValueError as exc:
            return {"error": str(exc)}

        return {"semantic_query": semantic_query, "error": None}

    def _route_after_validate(self, state: GraphState) -> str:
        if state.get("error") is None:
            return "execute"

        if state.get("attempts", 0) >= MAX_RETRIES:
            return "give_up"

        return "retry"

    # ------------------------------------------------------
    # Node：執行查詢
    # ------------------------------------------------------

    def _execute_node(self, state: GraphState) -> dict:
        result = self.query_service.execute(state["semantic_query"])
        return {"result": result}

    # ------------------------------------------------------
    # Public
    # ------------------------------------------------------

    def run(self, question: str) -> dict:
        final_state = self.graph.invoke(
            {"question": question, "attempts": 0}
        )

        # 純聊天回覆
        if final_state.get("chat_reply") is not None:
            return {
                "success": True,
                "type": "chat",
                "reply": final_state["chat_reply"],
            }

        if final_state.get("error"):
            return {
                "success": False,
                "type": "query",
                "error": final_state["error"],
                "attempts": final_state.get("attempts", 0),
            }

        return {
            "success": True,
            "type": "query",
            "translated_query": final_state["semantic_query"].model_dump(),
            "result": final_state["result"],
            "attempts": final_state.get("attempts", 0),
        }





# import json
# import os
# from typing import Any, TypedDict

# from openai import OpenAI
# from langgraph.graph import END, START, StateGraph

# from app.schemas.semantic_query import SemanticQuery
# from app.semantic.mapper import SemanticMapper
# from app.semantic.query_builder import SemanticQueryBuilder
# from app.semantic.schema_description import build_schema_description
# from app.services.query_service import QueryService


# MAX_RETRIES = 2


# # ======================================================
# # Tool schema（OpenAI function-calling 格式）
# # ======================================================

# QUERY_TOOL = {
#     "type": "function",
#     "function": {
#         "name": "build_semantic_query",
#         "description": (
#             "根據使用者的自然語言問題，組出一個語義查詢（SemanticQuery）。"
#             "只能使用 schema 說明中列出的 entity 和欄位名稱，不可以自己發明。"
#         ),
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "entity": {
#                     "type": "string",
#                     "description": "要查詢的實體名稱，必須是 schema 中列出的其中一個",
#                 },
#                 "fields": {
#                     "type": "array",
#                     "items": {"type": "string"},
#                     "description": "要顯示的欄位（property 或 relation 名稱）",
#                 },
#                 "filters": {
#                     "type": "array",
#                     "items": {
#                         "type": "object",
#                         "properties": {
#                             "field": {"type": "string"},
#                             "operator": {
#                                 "type": "string",
#                                 "enum": [
#                                     "=", "!=", ">", ">=",
#                                     "<", "<=", "LIKE", "IN",
#                                 ],
#                             },
#                             "value": {},
#                         },
#                         "required": ["field", "operator", "value"],
#                     },
#                 },
#                 "order_by": {
#                     "type": "object",
#                     "properties": {
#                         "field": {"type": "string"},
#                         "direction": {
#                             "type": "string",
#                             "enum": ["ASC", "DESC"],
#                         },
#                     },
#                 },
#                 "limit": {
#                     "type": "integer",
#                     "description": "最多回傳幾筆，預設 20，最大 500",
#                 },
#             },
#             "required": ["entity"],
#         },
#     },
# }


# # ======================================================
# # Graph State
# # ======================================================

# class GraphState(TypedDict, total=False):
#     question: str
#     raw_query: dict[str, Any] | None
#     semantic_query: SemanticQuery
#     error: str | None
#     attempts: int
#     result: dict[str, Any]


# # ======================================================
# # NLQueryGraph
# # ======================================================

# class NLQueryGraph:
#     """
#     用 LangGraph 包裝「自然語言 -> SemanticQuery -> 執行查詢」的流程。
#     模型呼叫走 OpenAI 相容格式的自架 API，翻譯失敗時會自動
#     把錯誤訊息回饋給模型，重新翻譯一次（最多 MAX_RETRIES 次）。
#     """

#     def __init__(self, mapper: SemanticMapper, query_service: QueryService):
#         self.mapper = mapper
#         self.query_service = query_service
#         self.builder = SemanticQueryBuilder(mapper)

#         self.client = OpenAI(
#             base_url=os.environ["MY_MODEL_BASE_URL"],
#             api_key=os.environ.get("MY_MODEL_API_KEY", "not-needed"),
#         )
#         self.model_name = os.environ["MY_MODEL_NAME"]

#         self.schema_text = build_schema_description(mapper)
#         self.graph = self._build_graph()

#     # ------------------------------------------------------
#     # Graph 組裝
#     # ------------------------------------------------------

#     def _build_graph(self):
#         workflow = StateGraph(GraphState)

#         workflow.add_node("translate", self._translate_node)
#         workflow.add_node("validate", self._validate_node)
#         workflow.add_node("execute", self._execute_node)

#         workflow.add_edge(START, "translate")
#         workflow.add_edge("translate", "validate")

#         workflow.add_conditional_edges(
#             "validate",
#             self._route_after_validate,
#             {
#                 "retry": "translate",
#                 "execute": "execute",
#                 "give_up": END,
#             },
#         )

#         workflow.add_edge("execute", END)

#         return workflow.compile()

#     # ------------------------------------------------------
#     # Node：翻譯（自然語言 -> raw dict）
#     # ------------------------------------------------------

#     def _translate_node(self, state: GraphState) -> dict:
#         system_prompt = (
#             "你是查詢翻譯助手。使用者用中文問問題，"
#             "你要把它轉成結構化的語義查詢。\n\n"
#             f"目前系統可查詢的 entity 與欄位：\n\n{self.schema_text}\n"
#             "規則：\n"
#             "1. entity 和欄位名稱只能使用上面列出的名稱，不可以自己發明。\n"
#             "2. 模糊比對用 LIKE。\n"
#             "3. 一定要呼叫 build_semantic_query 工具回答，不要用文字回覆。"
#         )

#         user_content = state["question"]

#         # 如果是重試，把上一次的錯誤訊息一併告訴模型
#         if state.get("error"):
#             user_content += (
#                 f"\n\n（上一次你的回答有問題：{state['error']}，"
#                 f"請根據可用的欄位重新修正。）"
#             )

#         response = self.client.chat.completions.create(
#             model=self.model_name,
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_content},
#             ],
#             tools=[QUERY_TOOL],
#             tool_choice={
#                 "type": "function",
#                 "function": {"name": "build_semantic_query"},
#             },
#         )

#         message = response.choices[0].message
#         tool_calls = message.tool_calls

#         attempts = state.get("attempts", 0) + 1

#         if not tool_calls:
#             return {
#                 "raw_query": None,
#                 "error": "模型沒有回傳有效的查詢結構",
#                 "attempts": attempts,
#             }

#         try:
#             raw_query = json.loads(tool_calls[0].function.arguments)
#         except json.JSONDecodeError:
#             return {
#                 "raw_query": None,
#                 "error": "模型回傳的參數不是合法 JSON",
#                 "attempts": attempts,
#             }

#         return {
#             "raw_query": raw_query,
#             "attempts": attempts,
#         }

#     # ------------------------------------------------------
#     # Node：驗證（dict -> SemanticQuery，並確認 entity/field 真的存在）
#     # ------------------------------------------------------

#     def _validate_node(self, state: GraphState) -> dict:
#         raw_query = state.get("raw_query")

#         if raw_query is None:
#             return {"error": state.get("error", "翻譯失敗")}

#         try:
#             semantic_query = SemanticQuery(**raw_query)
#         except Exception as exc:
#             return {"error": f"查詢格式不正確：{exc}"}

#         # 真正驗證 entity / fields / filters 是否存在於 mapper 中
#         try:
#             self.builder.build(semantic_query)
#         except ValueError as exc:
#             return {"error": str(exc)}

#         return {"semantic_query": semantic_query, "error": None}

#     def _route_after_validate(self, state: GraphState) -> str:
#         if state.get("error") is None:
#             return "execute"

#         if state.get("attempts", 0) >= MAX_RETRIES:
#             return "give_up"

#         return "retry"

#     # ------------------------------------------------------
#     # Node：執行查詢
#     # ------------------------------------------------------

#     def _execute_node(self, state: GraphState) -> dict:
#         result = self.query_service.execute(state["semantic_query"])
#         return {"result": result}

#     # ------------------------------------------------------
#     # Public
#     # ------------------------------------------------------

#     def run(self, question: str) -> dict:
#         final_state = self.graph.invoke(
#             {"question": question, "attempts": 0}
#         )

#         if final_state.get("error"):
#             return {
#                 "success": False,
#                 "error": final_state["error"],
#                 "attempts": final_state.get("attempts", 0),
#             }

#         return {
#             "success": True,
#             "translated_query": final_state["semantic_query"].model_dump(),
#             "result": final_state["result"],
#             "attempts": final_state.get("attempts", 0),
#         }