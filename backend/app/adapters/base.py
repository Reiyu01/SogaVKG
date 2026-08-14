"""
規範後續Adapter需要提供何種規格
"""



from abc import ABC, abstractmethod
from typing import Any


class DatabaseAdapter(ABC):

    @abstractmethod
    def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """執行查詢並回傳 dict list。"""
        raise NotImplementedError

    @abstractmethod
    def execute_one(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """執行查詢並取得單筆資料。"""
        raise NotImplementedError

    @abstractmethod
    def execute_write(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> int:
        """執行 INSERT / UPDATE / DELETE。"""
        raise NotImplementedError