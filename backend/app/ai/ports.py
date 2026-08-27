from typing import Protocol, runtime_checkable


class ModelDependencyError(RuntimeError):
    """The configured model provider could not complete a bounded call."""


@runtime_checkable
class ChatModelPort(Protocol):
    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
    ) -> str: ...
