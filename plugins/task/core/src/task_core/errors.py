from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TaskError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def result(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {"code": self.code, "message": self.message, "details": self.details},
        }


def success(data: dict[str, Any], warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"ok": True, "data": data, "warnings": warnings or []}
