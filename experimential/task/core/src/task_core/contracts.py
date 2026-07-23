from datetime import datetime
from typing import Annotated, Any, Literal

import msgspec

Unset = msgspec.UnsetType
CreatedAt = Annotated[
    datetime,
    msgspec.Meta(
        tz=True,
        description=(
            "Only set this when creating a historical Task with a known timezone-aware original timestamp. "
            "For ordinary Task creation, omit this field so Core uses the actual creation time. "
            "When set, it controls managed created_at, UUIDv7, and the top-level partition. "
            "WAL still records the actual creation time."
        ),
    ),
]
Actor = Annotated[
    str,
    msgspec.Meta(
        description=(
            "Best-effort Agent/model context, not authenticated identity. Use the most specific available value: "
            "an adapter's exact runtime model ID, the Agent's exact current-context model, or the best-supported "
            "model or family name. Omit only when no model information is available so Core can use <host>:unknown."
        ),
    ),
]


class FindRequest(msgspec.Struct, forbid_unknown_fields=True):
    query: str = ""
    branch: str | None | Unset = msgspec.UNSET
    statuses: list[Literal["open", "paused", "closed"]] = msgspec.field(
        default_factory=lambda: ["open", "paused", "closed"]
    )
    include_archived: bool = False
    limit: int = 20
    cwd: str | Unset = msgspec.UNSET


class ReadRequest(msgspec.Struct, forbid_unknown_fields=True):
    task_ref: str
    view: Literal["metadata", "summary", "detailed"] = "summary"
    wal_max_length: int | Unset = msgspec.UNSET
    wal_max_entries: int | None | Unset = msgspec.UNSET
    cwd: str | Unset = msgspec.UNSET


class TaskItem(msgspec.Struct, forbid_unknown_fields=True):
    name: str
    body: str | Unset = msgspec.UNSET
    created_at: CreatedAt | Unset = msgspec.UNSET
    branch: str | Unset = msgspec.UNSET
    depends_on: list[str] | Unset = msgspec.UNSET
    related_to: list[str] | Unset = msgspec.UNSET
    extra: dict[str, Any] | Unset = msgspec.UNSET


class CreateTaskRequest(msgspec.Struct, tag="task", tag_field="type", forbid_unknown_fields=True):
    task: TaskItem
    user_confirmed: bool = False
    actor: Actor | Unset = msgspec.UNSET
    cwd: str | Unset = msgspec.UNSET


class CreateSubtasksRequest(msgspec.Struct, tag="subtasks", tag_field="type", forbid_unknown_fields=True):
    parent_ref: str
    subtasks: list[TaskItem]
    actor: Actor | Unset = msgspec.UNSET
    cwd: str | Unset = msgspec.UNSET


CreateRequest = CreateTaskRequest | CreateSubtasksRequest


class RelationDelta(msgspec.Struct, forbid_unknown_fields=True):
    add: list[str] = msgspec.field(default_factory=list)
    remove: list[str] = msgspec.field(default_factory=list)


class ExtraDelta(msgspec.Struct, forbid_unknown_fields=True):
    set: dict[str, Any] = msgspec.field(default_factory=dict)
    remove: list[str] = msgspec.field(default_factory=list)


class Transition(msgspec.Struct, forbid_unknown_fields=True):
    status: Literal["open", "paused", "closed"]
    reason: str
    force: bool = False


class Archive(msgspec.Struct, forbid_unknown_fields=True):
    reason: str


class Unarchive(msgspec.Struct, forbid_unknown_fields=True):
    reason: str
    user_confirmed: bool


class UpdatePatch(msgspec.Struct, forbid_unknown_fields=True):
    branch: str | None | Unset = msgspec.UNSET
    depends_on: RelationDelta | Unset = msgspec.UNSET
    related_to: RelationDelta | Unset = msgspec.UNSET
    extra: ExtraDelta | Unset = msgspec.UNSET
    transition: Transition | Unset = msgspec.UNSET
    archive: Archive | Unset = msgspec.UNSET
    unarchive: Unarchive | Unset = msgspec.UNSET


class UpdateRequest(msgspec.Struct, forbid_unknown_fields=True):
    task_ref: str
    patch: UpdatePatch
    actor: Actor | Unset = msgspec.UNSET
    cwd: str | Unset = msgspec.UNSET


class LogRequest(msgspec.Struct, forbid_unknown_fields=True):
    task_ref: str
    message: str
    extra_body: str | Unset = msgspec.UNSET
    actor: Actor | Unset = msgspec.UNSET
    cwd: str | Unset = msgspec.UNSET


REQUEST_TYPES: dict[str, Any] = {
    "task_find": FindRequest,
    "task_read": ReadRequest,
    "task_create": CreateRequest,
    "task_update": UpdateRequest,
    "task_log": LogRequest,
}


def validate(operation: str, value: dict[str, Any]) -> None:
    request_type = REQUEST_TYPES.get(operation)
    if request_type is None:
        return
    msgspec.convert(value, request_type)


def schemas() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, request_type in REQUEST_TYPES.items():
        raw = msgspec.json.schema(request_type)
        definitions = raw.get("$defs", {})
        normalized = _dereference(raw, definitions)
        if name == "task_create":
            # Agent hosts require an object at the tool schema root. Core still validates the exact
            # tagged union, so this presentation schema may safely expose the union's combined fields.
            branches = normalized.pop("anyOf")
            properties: dict[str, Any] = {}
            for branch in branches:
                properties.update(branch.get("properties", {}))
            properties["type"] = {"type": "string", "enum": ["task", "subtasks"]}
            normalized = {
                "type": "object",
                "properties": properties,
                "required": ["type"],
                "additionalProperties": False,
            }
        result[name] = _host_compatible(normalized)
    return result


def _dereference(value: Any, definitions: dict[str, Any]) -> Any:
    if isinstance(value, list):
        return [_dereference(item, definitions) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        name = value["$ref"].removeprefix("#/$defs/")
        return _dereference(definitions[name], definitions)
    return {
        key: _dereference(item, definitions) for key, item in value.items() if key not in {"$defs", "discriminator"}
    }


def _host_compatible(value: Any) -> Any:
    if isinstance(value, list):
        return [_host_compatible(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _host_compatible(item) for key, item in value.items()}
    if result.get("required") == []:
        result.pop("required")
    enum = result.get("enum")
    if enum and all(isinstance(item, str) for item in enum):
        result.setdefault("type", "string")
    return result
