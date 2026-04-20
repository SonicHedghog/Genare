from typing import Any, Literal, TypedDict


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: Any


class Attachment(TypedDict):
    kind: str
    name: str
    path: str
    content: str
    data_url: str
