from openai import OpenAI

from app.ai.ports import ModelDependencyError


class OpenAICompatibleChatModel:
    """OpenAI-compatible Chat Completions adapter behind a project-owned port."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
    ) -> str:
        if not self.api_key:
            raise ModelDependencyError("model dependency unavailable")
        try:
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=timeout_seconds,
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
            )
            content = response.choices[0].message.content
            if not content:
                raise ModelDependencyError("model returned no content")
            return content
        except ModelDependencyError:
            raise
        except Exception as exc:
            raise ModelDependencyError("model dependency unavailable") from exc
