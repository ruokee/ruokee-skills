import base64
import fcntl
import os
import re
import tempfile
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from uuid import UUID

from ruamel.yaml.comments import TaggedScalar
from wcwidth import wcswidth

from task_core import SCHEMA_VERSION
from task_core.config import Config, load_config, load_registry
from task_core.errors import TaskError
from task_core.yamlio import TaskDocument, dump_task_document, load_task_document

_EXPECTED_UNSET = object()


@dataclass(slots=True)
class ProjectContext:
    project_root: Path
    task_root: Path
    config: Config
    mode: str


@dataclass(slots=True)
class TaskRecord:
    task_dir: Path
    document: TaskDocument | None
    metadata: dict[str, Any]
    errors: list[dict[str, str]]
    warnings: list[dict[str, Any]]
    parent_id: str | None = None

    @property
    def valid(self) -> bool:
        return not self.errors and self.document is not None

    @property
    def id(self) -> str:
        return str(self.metadata.get("id", ""))


def canonical(path: Path) -> Path:
    return path.expanduser().resolve()


def find_git_root(start: Path) -> Path | None:
    for path in [start, *start.parents]:
        if (path / ".git").exists():
            return path
    return None


def discover_project(cwd: Path) -> ProjectContext:
    cwd = canonical(cwd)
    registry = load_registry()
    embedded: list[ProjectContext] = []
    detached: list[ProjectContext] = []
    boundary = find_git_root(cwd)
    for path in [cwd, *cwd.parents]:
        config = load_config(path)
        task_root = canonical(path / config.task_root)
        if task_root != path and path not in task_root.parents:
            raise TaskError(
                "task_root_outside_project",
                "embedded task_root 解析后必须位于 project root 内",
                {"project_root": str(path), "task_root": str(task_root)},
            )
        if task_root.is_dir():
            embedded.append(ProjectContext(path, task_root, config, "embedded"))
        slug = registry.get(str(path))
        if slug:
            detached.append(ProjectContext(path, canonical(config.data_dir / slug), config, "detached"))
        if path == boundary:
            break
    evidence = embedded + detached
    if not evidence:
        raise TaskError("project_not_initialized", "当前 worksite 尚未初始化 Task")
    nearest_depth = max(len(item.project_root.parts) for item in evidence)
    nearest = [item for item in evidence if len(item.project_root.parts) == nearest_depth]
    signatures = {(item.project_root, item.task_root, item.mode) for item in nearest}
    if len(signatures) != 1:
        raise TaskError(
            "root_conflict",
            "发现互相冲突的 Task root 证据",
            {"candidates": [str(item.task_root) for item in nearest]},
        )
    selected = nearest[0]
    if selected.mode == "detached" and not selected.task_root.is_dir():
        raise TaskError(
            "task_root_missing",
            "detached registry 对应的 Task root 不存在",
            {"task_root": str(selected.task_root)},
        )
    return selected


def validate_name(name: object) -> str:
    if not isinstance(name, str):
        raise TaskError("task_name_invalid", "Task name 必须是字符串")
    normalized = unicodedata.normalize("NFC", name).strip()
    if not normalized or "\x00" in normalized or "\n" in normalized or "\r" in normalized:
        raise TaskError("task_name_invalid", "Task name 不能为空或包含 NUL/换行")
    if wcswidth(normalized) > 40 or len(normalized.encode()) > 96:
        raise TaskError("task_name_too_long", "Task name 超过 40 显示宽度或 96 UTF-8 bytes")
    return normalized


def slugify(name: str) -> str:
    output: list[str] = []
    for char in name:
        if char in "/\\" or char.isspace() or ord(char) < 32 or ord(char) == 127:
            output.append("-")
        else:
            output.append(char)
    slug = re.sub(r"-+", "-", "".join(output)).strip("-.")
    if not slug:
        raise TaskError("task_slug_invalid", "Task name 无法生成有效目录 slug")
    return slug


def _validate_metadata(metadata: dict[str, Any], path: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    def fail(field: str, message: str) -> None:
        errors.append({"field": field, "message": message})

    if metadata.get("schema_version") != SCHEMA_VERSION:
        fail("schema_version", f"只支持 schema {SCHEMA_VERSION}")
    try:
        identifier = UUID(str(metadata.get("id")))
        if identifier.version != 7:
            fail("id", "id 必须是完整 UUIDv7")
    except (ValueError, TypeError, AttributeError):
        fail("id", "id 必须是完整 UUIDv7")
    try:
        validate_name(metadata.get("name"))
    except TaskError as exc:
        fail("name", exc.message)
    if metadata.get("status") not in {"open", "paused", "closed"}:
        fail("status", "status 必须是 open、paused 或 closed")
    if not isinstance(metadata.get("archived", False), bool):
        fail("archived", "archived 必须是 boolean")
    elif metadata.get("archived", False) and metadata.get("status") != "closed":
        fail("archived", "只有 closed Task 可以 archived")
    try:
        created = datetime.fromisoformat(str(metadata.get("created_at")))
        if created.tzinfo is None:
            fail("created_at", "created_at 必须带时区")
    except ValueError:
        fail("created_at", "created_at 必须是 RFC 3339 时间")
    for field in ("depends_on", "related_to"):
        value = metadata.get(field, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            fail(field, f"{field} 必须是完整 Task ID 列表")
        elif any(not is_uuid7(item) for item in value):
            fail(field, f"{field} 只能包含完整 UUIDv7")
    if "branch" in metadata and metadata["branch"] is not None and not isinstance(metadata["branch"], str):
        fail("branch", "branch 必须是字符串")
    if "last_transition_reason" in metadata and not isinstance(metadata["last_transition_reason"], str):
        fail("last_transition_reason", "last_transition_reason 必须是字符串")
    if "extra" in metadata:
        if not isinstance(metadata["extra"], dict):
            fail("extra", "extra 必须是 mapping")
        elif not all(isinstance(key, str) for key in metadata["extra"]):
            fail("extra", "extra 的 key 必须是字符串")
    return errors


def load_record(task_dir: Path) -> TaskRecord:
    warnings: list[dict[str, Any]] = []
    try:
        document = load_task_document(task_dir / "TASK.md")
    except TaskError as exc:
        return TaskRecord(task_dir, None, {}, [{"field": "frontmatter", "message": exc.message}], warnings)
    metadata = _plain_value(document.metadata)
    metadata.setdefault("archived", False)
    metadata.setdefault("depends_on", [])
    metadata.setdefault("related_to", [])
    errors = _validate_metadata(metadata, task_dir)
    raw_extra = document.metadata.get("extra")
    if isinstance(raw_extra, dict) and not all(isinstance(key, str) for key in raw_extra):
        errors.append({"field": "extra", "message": "extra 的 key 必须是字符串"})
    if not errors:
        expected = slugify(str(metadata["name"]))
        actual = task_dir.name.split("--", 1)[-1]
        if expected != actual:
            warnings.append({"code": "name_slug_mismatch", "expected": expected, "actual": actual})
    return TaskRecord(task_dir, document, metadata, errors, warnings)


def _plain_value(value: Any) -> Any:
    """Expose JSON-safe semantics while retaining round-trip nodes in TaskDocument."""
    if isinstance(value, TaggedScalar):
        return _plain_value(value.value)
    if isinstance(value, dict):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_plain_value(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value


def discover_tasks(context: ProjectContext, *, penetrate_closed: bool = False) -> list[TaskRecord]:
    records: list[TaskRecord] = []
    stack: list[tuple[Path, str | None]] = [(context.task_root, None)]
    seen_ids: dict[str, Path] = {}
    while stack:
        directory, parent_id = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name, reverse=True)
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False) or entry.name == ".cache":
                continue
            path = Path(entry.path)
            task_file = path / "TASK.md"
            is_task = task_file.is_file() and not task_file.is_symlink()
            child_parent = parent_id
            descend = True
            if is_task:
                record = load_record(path)
                record.parent_id = parent_id
                records.append(record)
                if record.valid:
                    if not _is_canonical_task_path(context, record, parent_id):
                        record.warnings.append({"code": "noncanonical_task_path", "path": str(path)})
                    if record.id in seen_ids:
                        record.errors.append({"field": "id", "message": "project 中存在重复 Task UUID"})
                    else:
                        seen_ids[record.id] = path
                    child_parent = record.id
                    if record.metadata.get("status") == "closed" and not penetrate_closed:
                        descend = False
            if descend:
                stack.append((path, child_parent))
    return records


def _is_canonical_task_path(context: ProjectContext, record: TaskRecord, parent_id: str | None) -> bool:
    leaf = rf"^\d{{2}}--{re.escape(slugify(str(record.metadata['name'])))}$"
    if re.fullmatch(leaf, record.task_dir.name) is None:
        return False
    if parent_id is not None:
        return record.task_dir.parent.name == "subtasks"
    try:
        relative = record.task_dir.relative_to(context.task_root)
    except ValueError:
        return False
    return (
        len(relative.parts) == 3
        and re.fullmatch(r"\d{4}-\d{2}", relative.parts[0]) is not None
        and re.fullmatch(r"\d{2}", relative.parts[1]) is not None
    )


def require_unique_record(context: ProjectContext, task_ref: str) -> TaskRecord:
    direct = Path(task_ref).expanduser()
    if direct.is_absolute() or "/" in task_ref:
        candidate = direct if direct.is_absolute() else context.project_root / direct
        candidate = canonical(candidate)
        if candidate.is_file() and candidate.name == "TASK.md":
            candidate = candidate.parent
        if (candidate / "TASK.md").is_file():
            if candidate != context.task_root and context.task_root not in candidate.parents:
                raise TaskError(
                    "task_cross_project",
                    "Task 路径不属于当前 project Task root",
                    {"task_dir": str(candidate), "task_root": str(context.task_root)},
                )
            record = load_record(candidate)
            if record.id:
                duplicates = [item for item in discover_tasks(context, penetrate_closed=True) if item.id == record.id]
                if len(duplicates) > 1:
                    raise TaskError(
                        "task_ref_ambiguous",
                        f"Task UUID 在 project 中不唯一：{record.id}",
                        {"candidates": [str(item.task_dir) for item in duplicates]},
                    )
            return record
    records = discover_tasks(context, penetrate_closed=True)
    normalized_ref = task_ref.lower() if is_uuid7(task_ref) else task_ref
    matches = [
        record
        for record in records
        if normalized_ref in {record.id, str(record.metadata.get("name", "")), record.task_dir.name}
    ]
    if not matches:
        raise TaskError("task_not_found", f"找不到 Task：{task_ref}")
    if len(matches) > 1:
        raise TaskError(
            "task_ref_ambiguous",
            f"Task 引用不唯一：{task_ref}",
            {"candidates": [str(item.task_dir) for item in matches]},
        )
    selected = matches[0]
    duplicates = [item for item in records if selected.id and item.id == selected.id]
    if len(duplicates) > 1:
        raise TaskError(
            "task_ref_ambiguous",
            f"Task UUID 在 project 中不唯一：{selected.id}",
            {"candidates": [str(item.task_dir) for item in duplicates]},
        )
    return selected


def require_valid(record: TaskRecord) -> None:
    if not record.valid:
        raise TaskError(
            "task_managed_fields_invalid",
            "TASK.md managed fields 非法，不能执行修改",
            {"task_dir": str(record.task_dir), "errors": record.errors},
        )


def atomic_write(path: Path, content: bytes, *, expected: bytes | None | object = _EXPECTED_UNSET) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if expected is not _EXPECTED_UNSET:
        current = path.read_bytes() if path.exists() else None
        if current != expected:
            raise TaskError("external_write_race", "目标文件在写入前被外部修改", {"path": str(path)})
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, staging = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staging, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(staging)


def write_record(record: TaskRecord) -> None:
    if record.document is None:
        raise TaskError("task_managed_fields_invalid", "缺少可写 TASK.md")
    content = dump_task_document(record.document)
    atomic_write(record.task_dir / "TASK.md", content, expected=record.document.source_bytes)
    record.document.source_bytes = content


@contextmanager
def directory_lock(directory: Path) -> Iterator[None]:
    try:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    except OSError as exc:
        raise TaskError("lock_target_changed", "加锁目标在操作前发生变化", {"path": str(directory)}) from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def top_task_dir(context: ProjectContext, record: TaskRecord) -> Path:
    records = {item.id: item for item in discover_tasks(context, penetrate_closed=True) if item.valid}
    current = record
    while current.parent_id and current.parent_id in records:
        current = records[current.parent_id]
    return current.task_dir


def is_uuid7(value: str) -> bool:
    try:
        identifier = UUID(value)
        return identifier.version == 7 and str(identifier) == value.lower()
    except (ValueError, AttributeError):
        return False
