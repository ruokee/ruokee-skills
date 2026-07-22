import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Iterable
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import msgspec
from ruamel.yaml.comments import CommentedMap

from task_core import PROTOCOL_VERSION, SCHEMA_VERSION, VERSION
from task_core.config import load_config, load_registry, registry_path
from task_core.contracts import CreatedAt
from task_core.contracts import validate as validate_contract
from task_core.errors import TaskError, success
from task_core.store import (
    ProjectContext,
    TaskRecord,
    atomic_write,
    canonical,
    directory_lock,
    discover_project,
    discover_tasks,
    find_git_root,
    is_uuid7,
    load_record,
    require_unique_record,
    require_valid,
    slugify,
    top_task_dir,
    validate_name,
    write_record,
)
from task_core.yamlio import TaskDocument, dump_task_document, dump_yaml

WAL_HEADER = re.compile(r"^## (\d{4}-\d{2}-\d{2}T[^\n]+) · ([^\n]+)$", re.MULTILINE)


def now_local() -> datetime:
    return datetime.now().astimezone()


def iso_now() -> str:
    return now_local().isoformat(timespec="milliseconds")


def normalize_actor(actor: object) -> str:
    if actor is None or actor == "":
        return f"{os.environ.get('TASK_HOST', 'core')}:unknown"
    if not isinstance(actor, str) or "\n" in actor or "\r" in actor or " · " in actor:
        raise TaskError("actor_invalid", "actor 必须是单行字符串且不能包含分隔符 ` · `")
    return actor


def _append_line(path: Path, line: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if line in existing.splitlines():
        return
    separator = "" if not existing or existing.endswith("\n") else "\n"
    atomic_write(path, f"{existing}{separator}{line}\n".encode())


def init_project(
    *,
    project_root: str | None = None,
    cwd: str | None = None,
    mode: str | None = None,
    git_policy: str | None = None,
    project_slug: str | None = None,
) -> dict[str, Any]:
    start = canonical(Path(project_root or cwd or os.getcwd()))
    root = start if project_root else find_git_root(start) or start
    config = load_config(root)
    selected_mode = mode or config.mode
    selected_policy = git_policy or config.git_policy
    if selected_mode not in {"embedded", "detached"}:
        raise TaskError("config_invalid", "mode 必须是 embedded 或 detached")
    if selected_policy not in {"ignore", "track", "none"}:
        raise TaskError("config_invalid", "git_policy 必须是 ignore、track 或 none")

    if selected_mode == "embedded":
        task_root = canonical(root / config.task_root)
        if task_root != root and root not in task_root.parents:
            raise TaskError(
                "task_root_outside_project",
                "embedded task_root 解析后必须位于 project root 内",
                {"project_root": str(root), "task_root": str(task_root)},
            )
        with directory_lock(root):
            if selected_policy == "track":
                ignored = subprocess.run(
                    ["git", "check-ignore", "--no-index", "-q", str(task_root / ".task-policy-probe")],
                    cwd=root,
                    check=False,
                )
                if ignored.returncode == 0 or (task_root / ".gitignore").exists():
                    raise TaskError("git_policy_conflict", "Task root 当前被 Git ignore，不能直接切换为 track")
            task_root.mkdir(parents=True, exist_ok=True)
            _init_cache(task_root)
            if selected_policy == "ignore":
                _append_line(task_root / ".gitignore", "*")
                project_config = root / ".agents/task.yaml"
                if project_config.exists():
                    _append_line(project_config.parent / ".gitignore", project_config.name)
                    _append_line(project_config.parent / ".gitignore", ".gitignore")
        return success({"project_root": str(root), "task_root": str(task_root), "mode": selected_mode})

    slug = project_slug or root.name
    if not slug or "/" in slug or "\\" in slug or slug in {".", ".."}:
        raise TaskError("project_slug_invalid", "project_slug 必须是单个非空路径组件")
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with directory_lock(root), directory_lock(path.parent):
        previous = path.read_bytes() if path.exists() else None
        registry = load_registry()
        canonical_root = str(canonical(root))
        existing = registry.get(canonical_root)
        if existing:
            slug = existing
        elif slug in registry.values():
            owner = next(key for key, value in registry.items() if value == slug)
            raise TaskError("project_slug_conflict", "project_slug 已由其他 project 使用", {"owner": owner})
        task_root = canonical(config.data_dir / slug)
        task_root.mkdir(parents=True, exist_ok=True)
        _init_cache(task_root)
        registry[canonical_root] = slug
        atomic_write(path, dump_yaml({"projects": registry}).encode(), expected=previous)
    return success(
        {"project_root": str(root), "task_root": str(task_root), "mode": selected_mode, "project_slug": slug}
    )


def _init_cache(task_root: Path) -> None:
    cache = task_root / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    _append_line(cache / ".gitignore", "*")
    tag = cache / "CACHEDIR.TAG"
    if not tag.exists():
        atomic_write(tag, b"Signature: 8a477f597d28d172789f06886806bc55\n")


def _record_summary(record: TaskRecord, *, match: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "id": record.id,
        "name": record.metadata.get("name"),
        "status": record.metadata.get("status"),
        "archived": record.metadata.get("archived"),
        "task_dir": str(canonical(record.task_dir)),
        "parent_id": record.parent_id,
        "branch": record.metadata.get("branch"),
    }
    if match:
        value["match"] = match
    return value


def task_find(request: dict[str, Any], *, cwd: str | None = None) -> dict[str, Any]:
    context = discover_project(Path(cwd or request.get("cwd") or os.getcwd()))
    query = request.get("query", "")
    branch = request.get("branch")
    statuses = request.get("statuses", ["open", "paused", "closed"])
    include_archived = request.get("include_archived", False)
    limit = request.get("limit", 20)
    if not isinstance(query, str) or (branch is not None and not isinstance(branch, str)):
        raise TaskError("request_invalid", "query 和 branch 必须是字符串")
    if not isinstance(statuses, list) or not set(statuses) <= {"open", "paused", "closed"}:
        raise TaskError("request_invalid", "statuses 包含非法状态")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise TaskError("request_invalid", "limit 必须是 1..100")
    candidates: list[tuple[int, str, TaskRecord]] = []
    folded = query.casefold()
    warnings: list[dict[str, Any]] = []
    penetrate_closed = is_uuid7(query) or (bool(query) and (Path(query).is_absolute() or "/" in query))
    for record in discover_tasks(context, penetrate_closed=penetrate_closed):
        if not record.valid:
            warnings.append(
                {"code": "task_candidate_invalid", "task_dir": str(record.task_dir), "errors": record.errors}
            )
            continue
        if record.metadata["status"] not in statuses:
            continue
        if record.metadata["archived"] and not include_archived:
            continue
        if branch is not None and record.metadata.get("branch") != branch:
            continue
        score = 3
        if query:
            values = [record.id, str(record.metadata["name"]), record.task_dir.name, str(record.task_dir)]
            folded_values = [value.casefold() for value in values]
            if folded in folded_values:
                score = 0
            elif any(value.startswith(folded) for value in folded_values):
                score = 1
            elif any(folded in value for value in folded_values):
                score = 2
            else:
                continue
        candidates.append((score, str(record.metadata["created_at"]), record))
    candidates.sort(key=lambda item: (item[0], item[1], item[2].id))
    truncated = len(candidates) > limit
    data = [
        _record_summary(record, match={0: "exact", 1: "prefix", 2: "substring", 3: "listed"}[score])
        for score, _, record in candidates[:limit]
    ]
    return success(
        {
            "project_root": str(context.project_root),
            "task_root": str(context.task_root),
            "tasks": data,
            "truncated": truncated,
        },
        warnings,
    )


def _parse_wal(record: TaskRecord) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    wal_dir = record.task_dir / "wal"
    if not wal_dir.is_dir():
        return entries, warnings
    for path in sorted(wal_dir.glob("*.md")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            warnings.append({"code": "wal_invalid_utf8", "path": str(path)})
            continue
        matches = list(WAL_HEADER.finditer(text))
        prefix = text[: matches[0].start()] if matches else text
        if prefix.strip() or (not matches and text.strip()):
            warnings.append({"code": "wal_unparsed_text", "path": str(path)})
        for index, match in enumerate(matches):
            body = text[match.end() : matches[index + 1].start() if index + 1 < len(matches) else None].strip()
            timestamp = match.group(1)
            try:
                parsed = datetime.fromisoformat(timestamp)
                if parsed.tzinfo is None:
                    raise ValueError
            except ValueError:
                warnings.append({"code": "wal_invalid_timestamp", "path": str(path), "timestamp": timestamp})
                continue
            entries.append({"timestamp": timestamp, "actor": match.group(2), "body": body, "path": str(path)})
    entries.sort(key=lambda item: datetime.fromisoformat(item["timestamp"]))
    return entries, warnings


def _budget_wal(
    entries: list[dict[str, Any]], view: str, max_length: int, max_entries: int | None
) -> tuple[list[dict[str, Any]], bool]:
    if max_entries == 0 or max_length == 0:
        return [], bool(entries)
    selected: list[dict[str, Any]] = []
    used = 0
    for source in reversed(entries):
        entry = dict(source)
        if view == "summary":
            paragraphs = re.split(r"\n\s*\n", entry["body"], maxsplit=1)
            entry["body"] = paragraphs[0]
        rendered = f"## {entry['timestamp']} · {entry['actor']}\n\n{entry['body']}"
        if not selected and len(rendered) > max_length:
            header_length = len(rendered) - len(entry["body"])
            if header_length > max_length:
                break
            entry["body"] = entry["body"][: max_length - header_length]
            entry["truncated"] = True
            selected.append(entry)
            break
        if used + len(rendered) > max_length:
            break
        selected.append(entry)
        used += len(rendered)
        if max_entries is not None and len(selected) >= max_entries:
            break
    selected.reverse()
    return selected, len(selected) < len(entries)


def _topology(context: ProjectContext, record: TaskRecord) -> dict[str, Any]:
    records = [item for item in discover_tasks(context, penetrate_closed=True) if item.valid]
    by_id = {item.id: item for item in records}
    children = [_record_summary(item) for item in records if item.parent_id == record.id]
    dependents = [_record_summary(item) for item in records if record.id in item.metadata.get("depends_on", [])]
    related_from = [_record_summary(item) for item in records if record.id in item.metadata.get("related_to", [])]

    def resolve(ids: Iterable[str], relation: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        result: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        for identifier in ids:
            target = by_id.get(identifier)
            if target:
                result.append(_record_summary(target))
            else:
                warnings.append({"code": f"{relation}_missing", "task_id": identifier})
        return result, warnings

    depends, depends_warnings = resolve(record.metadata.get("depends_on", []), "dependency")
    related, related_warnings = resolve(record.metadata.get("related_to", []), "related")
    return {
        "parent": _record_summary(by_id[record.parent_id]) if record.parent_id in by_id else None,
        "children": children,
        "depends_on": depends,
        "dependents": dependents,
        "related_to": related,
        "related_from": related_from,
        "warnings": depends_warnings + related_warnings,
    }


def task_read(request: dict[str, Any], *, cwd: str | None = None) -> dict[str, Any]:
    context = discover_project(Path(cwd or request.get("cwd") or os.getcwd()))
    task_ref = request.get("task_ref")
    if not isinstance(task_ref, str) or not task_ref:
        raise TaskError("request_invalid", "task_ref 必填")
    view = request.get("view", "summary")
    if view not in {"metadata", "summary", "detailed"}:
        raise TaskError("request_invalid", "view 必须是 metadata、summary 或 detailed")
    record = require_unique_record(context, task_ref)
    data: dict[str, Any] = {
        "managed_valid": record.valid,
        "validation_errors": record.errors,
        "metadata": record.metadata,
        "task_dir": str(canonical(record.task_dir)),
        "project_root": str(context.project_root),
    }
    warnings = list(record.warnings)
    if record.valid:
        topology = _topology(context, record)
        warnings.extend(topology.pop("warnings"))
        data["topology"] = topology
    if view != "metadata":
        data["body"] = record.document.body.decode("utf-8") if record.document else ""
        entries, wal_warnings = _parse_wal(record)
        warnings.extend(wal_warnings)
        max_length = request.get("wal_max_length", context.config.wal_max_length)
        max_entries = request.get("wal_max_entries", context.config.wal_max_entries)
        if type(max_length) is not int or not 0 <= max_length <= 32000:
            raise TaskError("request_invalid", "wal_max_length 必须是 0..32000")
        if max_entries is not None and (type(max_entries) is not int or max_entries < 0):
            raise TaskError("request_invalid", "wal_max_entries 必须是非负整数或 null")
        data["wal"], data["wal_truncated"] = _budget_wal(entries, view, max_length, max_entries)
    return success(data, warnings)


def _task_partition(parent: Path, *, top_level: bool, date: datetime) -> Path:
    components = (date.strftime("%Y-%m"), date.strftime("%d")) if top_level else ("subtasks",)
    partition = parent
    for component in components:
        partition /= component
        if os.path.lexists(partition):
            if partition.is_symlink() or not partition.is_dir():
                raise TaskError("task_partition_invalid", "Task 创建分区必须是普通目录", {"path": str(partition)})
        else:
            partition.mkdir()
    return partition


def _next_slots(partition: Path, count: int, *, top_level: bool) -> list[int]:
    used = {
        int(match.group(1))
        for item in partition.iterdir()
        if (match := re.match(r"^(\d{2})--", item.name)) and item.is_dir() and not item.is_symlink()
    }
    available = [item for item in range(1, 100) if item not in used]
    if len(available) < count:
        raise TaskError("daily_task_limit" if top_level else "direct_subtask_limit", "Task 序号已用尽")
    max_used = max(used, default=0)
    preferred = [item for item in available if item > max_used]
    return (preferred + [item for item in available if item <= max_used])[:count]


def _new_document(item: dict[str, Any], created: datetime) -> TaskDocument:
    name = validate_name(item.get("name"))
    metadata = CommentedMap()
    metadata["schema_version"] = SCHEMA_VERSION
    metadata["id"] = str(uuid7_at(created))
    metadata["name"] = name
    metadata["status"] = "open"
    metadata["archived"] = False
    metadata["created_at"] = created.isoformat(timespec="milliseconds")
    for field in ("branch", "depends_on", "related_to", "extra"):
        if field in item and item[field] not in (None, [], {}):
            metadata[field] = item[field]
    body = item.get("body", "")
    if not isinstance(body, str):
        raise TaskError("request_invalid", "body 必须是字符串")
    return TaskDocument(metadata, body.encode(), "\n")


def _task_created_at(item: dict[str, Any], recorded_at: datetime) -> datetime:
    if "created_at" not in item:
        return recorded_at
    value = item["created_at"]
    if not isinstance(value, str):
        raise TaskError("request_invalid", "created_at 必须是带时区的 RFC 3339 时间")
    try:
        created_at = msgspec.convert(value, CreatedAt)
    except msgspec.ValidationError as exc:
        raise TaskError("request_invalid", "created_at 必须是带时区的 RFC 3339 时间") from exc
    return created_at


def _validate_initial_relations(context: ProjectContext, document: TaskDocument) -> None:
    records = {item.id: item for item in discover_tasks(context, penetrate_closed=True) if item.valid}
    for field in ("depends_on", "related_to"):
        value = document.metadata.get(field, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise TaskError("request_invalid", f"{field} 必须是 Task ID 列表")
        if any(not is_uuid7(item) for item in value):
            raise TaskError("request_invalid", f"{field} 只能包含完整 UUIDv7")
        missing = [item for item in value if item not in records]
        if missing:
            raise TaskError("relation_target_not_found", f"{field} 包含未知 Task", {"ids": missing})
        document.metadata[field] = list(dict.fromkeys(value))


def _wal_entry(timestamp: str, actor: str, message: str, extra_body: str | None = None) -> bytes:
    content = f"## {timestamp} · {actor}\n\n{message}"
    if extra_body:
        content += f"\n\n{extra_body}"
    return f"{content}\n".encode()


def task_create(request: dict[str, Any], *, cwd: str | None = None) -> dict[str, Any]:
    context = discover_project(Path(cwd or request.get("cwd") or os.getcwd()))
    kind = request.get("type")
    actor = normalize_actor(request.get("actor"))
    recorded_at = now_local()
    items: list[dict[str, Any]]
    parent_record: TaskRecord | None = None
    parent_ref: str | None = None
    if kind == "task":
        if context.config.creation_policy == "strict" and request.get("user_confirmed") is not True:
            raise TaskError("task_creation_confirmation_required", "strict 模式需要当前用户明确确认")
        item = request.get("task")
        if not isinstance(item, dict):
            raise TaskError("request_invalid", "task 必须是 object")
        top_level = True
        items = [item]
    elif kind == "subtasks":
        raw_parent_ref = request.get("parent_ref")
        raw_items = request.get("subtasks")
        if not isinstance(raw_parent_ref, str) or not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 50:
            raise TaskError("request_invalid", "subtasks 需要 parent_ref 和 1..50 个条目")
        parent_ref = raw_parent_ref
        if not all(isinstance(item, dict) for item in raw_items):
            raise TaskError("request_invalid", "每个 subtask 必须是 object")
        items = raw_items
        parent_record = require_unique_record(context, parent_ref)
        require_valid(parent_record)
        if parent_record.metadata["status"] not in {"open", "paused"}:
            raise TaskError("parent_not_active", "只有 open 或 paused parent 可以创建 subtask")
        top_level = False
    else:
        raise TaskError("request_invalid", "type 必须是 task 或 subtasks")

    created_times = [_task_created_at(item, recorded_at) for item in items]
    documents = [_new_document(item, created_at) for item, created_at in zip(items, created_times, strict=True)]
    names = [str(document.metadata["name"]) for document in documents]
    if len({slugify(name) for name in names}) != len(names):
        raise TaskError("directory_exists", "同一批次存在重复目录 slug")
    if top_level:
        lock_dir = context.project_root
    else:
        assert parent_record is not None
        lock_dir = top_task_dir(context, parent_record)
    warnings: list[dict[str, Any]] = []
    with directory_lock(lock_dir):
        if top_level:
            parent = context.task_root
        else:
            assert parent_ref is not None
            parent_record = require_unique_record(context, parent_ref)
            require_valid(parent_record)
            if parent_record.metadata["status"] not in {"open", "paused"}:
                raise TaskError("parent_not_active", "只有 open 或 paused parent 可以创建 subtask")
            parent = parent_record.task_dir
        for document in documents:
            _validate_initial_relations(context, document)
        partition_created = not top_level and not os.path.lexists(parent / "subtasks")
        partition = _task_partition(parent, top_level=top_level, date=created_times[0])
        slots = _next_slots(partition, len(documents), top_level=top_level)
        targets = [
            partition / f"{slot:02d}--{slugify(str(doc.metadata['name']))}"
            for slot, doc in zip(slots, documents, strict=True)
        ]
        if any(os.path.lexists(path) for path in targets):
            raise TaskError("directory_exists", "目标 Task 目录已经存在")
        staging: Path | None = None
        committed = False
        try:
            staging = Path(tempfile.mkdtemp(prefix=".task-create-", dir=partition))
            staged: list[Path] = []
            for target, document in zip(targets, documents, strict=True):
                current = staging / target.name
                current.mkdir()
                (current / "wal").mkdir()
                atomic_write(current / "TASK.md", dump_task_document(document))
                wal_path = current / "wal" / f"{recorded_at:%Y-%m-%d}.md"
                atomic_write(
                    wal_path,
                    _wal_entry(recorded_at.isoformat(timespec="milliseconds"), actor, "创建 Task。"),
                )
                staged.append(current)
            for current, target in zip(staged, targets, strict=True):
                os.replace(current, target)
            committed = True
        finally:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            if partition_created and not committed:
                with suppress(OSError):
                    partition.rmdir()
        created_records = [load_record(path) for path in targets]
        if parent_record is not None:
            try:
                _append_wal(parent_record, actor, f"批量创建 {len(created_records)} 个 subtask。")
            except TaskError as exc:
                warnings.append({"code": "wal_write_failed", "message": exc.message, "committed": True})
    return success({"created": [_record_summary(record) for record in created_records]}, warnings)


def _append_wal(record: TaskRecord, actor: str, message: str, extra_body: str | None = None) -> None:
    if "\n" in message or "\r" in message or not message.strip():
        raise TaskError("wal_message_invalid", "WAL message 必须是非空单行摘要")
    if extra_body is not None and not isinstance(extra_body, str):
        raise TaskError("wal_extra_body_invalid", "extra_body 必须是字符串")
    require_valid(record)
    stamp = now_local()
    wal_dir = record.task_dir / "wal"
    if os.path.lexists(wal_dir) and (wal_dir.is_symlink() or not wal_dir.is_dir()):
        raise TaskError("wal_not_directory", "wal 必须是普通目录", {"path": str(wal_dir)})
    wal_dir.mkdir(exist_ok=True)
    path = wal_dir / f"{stamp:%Y-%m-%d}.md"
    existed = os.path.lexists(path)
    if existed and (path.is_symlink() or not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode)):
        raise TaskError("wal_not_regular_file", "WAL 目标必须是普通文件", {"path": str(path)})
    existing = path.read_bytes() if existed else b""
    try:
        existing.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TaskError("wal_invalid_utf8", "WAL 文件必须是 UTF-8", {"path": str(path)}) from exc
    separator = b"\n" if existing and not existing.endswith(b"\n\n") else b""
    atomic_write(
        path,
        existing + separator + _wal_entry(stamp.isoformat(timespec="milliseconds"), actor, message, extra_body),
        expected=existing if existed else None,
    )


def task_log(request: dict[str, Any], *, cwd: str | None = None) -> dict[str, Any]:
    context = discover_project(Path(cwd or request.get("cwd") or os.getcwd()))
    task_ref, message = request.get("task_ref"), request.get("message")
    if not isinstance(task_ref, str) or not isinstance(message, str):
        raise TaskError("request_invalid", "task_ref 和 message 必填")
    actor = normalize_actor(request.get("actor"))
    record = require_unique_record(context, task_ref)
    require_valid(record)
    with directory_lock(top_task_dir(context, record)):
        record = require_unique_record(context, task_ref)
        _append_wal(record, actor, message, request.get("extra_body"))
    return success({"task_dir": str(record.task_dir), "logged": True})


def _relation_delta(metadata: dict[str, Any], field: str, delta: object) -> bool:
    if not isinstance(delta, dict) or set(delta) - {"add", "remove"}:
        raise TaskError("request_invalid", f"{field} 必须是 add/remove delta")
    add, remove = delta.get("add", []), delta.get("remove", [])
    if not isinstance(add, list) or not isinstance(remove, list) or not all(isinstance(x, str) for x in add + remove):
        raise TaskError("request_invalid", f"{field} add/remove 必须是 Task ID 列表")
    if any(not is_uuid7(item) for item in add + remove):
        raise TaskError("request_invalid", f"{field} add/remove 只能包含完整 UUIDv7")
    raw = list(metadata.get(field, []))
    old = list(dict.fromkeys(raw))
    new = [item for item in old if item not in set(remove)]
    new.extend(item for item in add if item not in new)
    if new == raw:
        return False
    metadata[field] = new
    return True


def _has_dependency_cycle(records: dict[str, TaskRecord], start: str, proposed: list[str]) -> bool:
    stack: list[tuple[str, set[str]]] = [(item, {start}) for item in proposed]
    while stack:
        current, path = stack.pop()
        if current in path:
            return True
        target = records.get(current)
        if target:
            stack.extend((item, path | {current}) for item in target.metadata.get("depends_on", []))
    return False


def _transition_checks(
    context: ProjectContext,
    record: TaskRecord,
    proposed: dict[str, Any],
    target: str,
    force: bool,
) -> list[dict[str, Any]]:
    bypassed: list[dict[str, Any]] = []
    if target != "closed":
        return bypassed
    records = [item for item in discover_tasks(context, penetrate_closed=True) if item.valid]
    by_id = {item.id: item for item in records}
    descendants: list[TaskRecord] = []
    frontier = [record.id]
    while frontier:
        parent = frontier.pop()
        children = [item for item in records if item.parent_id == parent]
        descendants.extend(children)
        frontier.extend(item.id for item in children)
    open_descendants = [item.id for item in descendants if item.metadata["status"] != "closed"]
    dependencies = proposed.get("depends_on", [])
    missing = [item for item in dependencies if item not in by_id]
    open_dependencies = [item for item in dependencies if item in by_id and by_id[item].metadata["status"] != "closed"]
    cycle = _has_dependency_cycle(by_id, record.id, dependencies)
    for code, ids in [
        ("descendants_not_closed", open_descendants),
        ("dependency_missing", missing),
        ("dependencies_not_closed", open_dependencies),
    ]:
        if ids:
            bypassed.append({"code": code, "ids": ids})
    if cycle:
        bypassed.append({"code": "dependency_cycle"})
    if bypassed and not force:
        raise TaskError("task_close_blocked", "Task 不满足正常关闭条件", {"checks": bypassed})
    return bypassed


def task_update(request: dict[str, Any], *, cwd: str | None = None) -> dict[str, Any]:
    context = discover_project(Path(cwd or request.get("cwd") or os.getcwd()))
    task_ref, patch = request.get("task_ref"), request.get("patch")
    if not isinstance(task_ref, str) or not isinstance(patch, dict):
        raise TaskError("request_invalid", "task_ref 和 patch 必填")
    allowed = {"branch", "depends_on", "related_to", "extra", "transition", "archive", "unarchive"}
    unknown = set(patch) - allowed
    if unknown:
        raise TaskError("request_invalid", "patch 含未知字段", {"fields": sorted(unknown)})
    actions = [item for item in ("transition", "archive", "unarchive") if item in patch]
    if len(actions) > 1:
        raise TaskError("request_invalid", "一次 update 最多包含一个生命周期动作")
    actor = normalize_actor(request.get("actor"))
    initial = require_unique_record(context, task_ref)
    require_valid(initial)
    with directory_lock(top_task_dir(context, initial)):
        record = require_unique_record(context, task_ref)
        require_valid(record)
        assert record.document is not None
        metadata = dict(record.metadata)
        changed_fields: list[str] = []
        if "branch" in patch:
            value = patch["branch"]
            if value is not None and not isinstance(value, str):
                raise TaskError("request_invalid", "branch 必须是字符串或 null")
            if metadata.get("branch") != value:
                if value is None:
                    metadata.pop("branch", None)
                else:
                    metadata["branch"] = value
                changed_fields.append("branch")
        for field in ("depends_on", "related_to"):
            if field in patch and _relation_delta(metadata, field, patch[field]):
                changed_fields.append(field)
        if "extra" in patch:
            delta = patch["extra"]
            if not isinstance(delta, dict) or set(delta) - {"set", "remove"}:
                raise TaskError("request_invalid", "extra 必须是浅层 set/remove delta")
            current = dict(metadata.get("extra", {}))
            set_values, remove = delta.get("set", {}), delta.get("remove", [])
            if (
                not isinstance(set_values, dict)
                or not isinstance(remove, list)
                or not all(isinstance(item, str) for item in remove)
                or not all(isinstance(item, str) for item in set_values)
            ):
                raise TaskError("request_invalid", "extra delta 非法")
            updated = {**current, **set_values}
            for key in remove:
                updated.pop(key, None)
            if updated != current:
                if updated:
                    metadata["extra"] = updated
                else:
                    metadata.pop("extra", None)
                changed_fields.append("extra")

        records = {item.id: item for item in discover_tasks(context, penetrate_closed=True) if item.valid}
        changed_relations = {field for field in ("depends_on", "related_to") if field in changed_fields}
        for field in changed_relations:
            values = metadata.get(field, [])
            if record.id in values:
                raise TaskError("relation_self", f"{field} 不允许指向自身")
            missing = [item for item in values if item not in records]
            if missing:
                raise TaskError("relation_target_not_found", f"{field} 包含未知 Task", {"ids": missing})
        if "depends_on" in changed_relations and _has_dependency_cycle(
            records, record.id, metadata.get("depends_on", [])
        ):
            raise TaskError("dependency_cycle", "depends_on 会形成依赖环")

        lifecycle_note: str | None = None
        bypassed: list[dict[str, Any]] = []
        if "transition" in patch:
            action = patch["transition"]
            if (
                not isinstance(action, dict)
                or not isinstance(action.get("reason"), str)
                or not action["reason"].strip()
            ):
                raise TaskError("transition_reason_required", "状态转移必须提供 reason")
            target, force = action.get("status"), action.get("force", False)
            if target not in {"open", "paused", "closed"} or not isinstance(force, bool):
                raise TaskError("request_invalid", "transition status/force 非法")
            if force and target != "closed":
                raise TaskError("request_invalid", "force 只能用于 close transition")
            current = metadata["status"]
            allowed_transitions = {
                ("open", "paused"),
                ("paused", "open"),
                ("open", "closed"),
                ("paused", "closed"),
                ("closed", "open"),
            }
            if (current, target) not in allowed_transitions:
                raise TaskError("transition_invalid", f"不允许从 {current} 转移到 {target}")
            if current == "closed" and metadata["archived"]:
                raise TaskError("archived_task_cannot_reopen", "archived Task 不能 reopen")
            bypassed = _transition_checks(context, record, metadata, target, force)
            metadata["status"] = target
            metadata["last_transition_reason"] = action["reason"]
            changed_fields.append("status")
            lifecycle_note = f"状态从 {current} 转为 {target}。原因：{action['reason']}"
            if bypassed:
                lifecycle_note += f" 强制绕过：{json.dumps(bypassed, ensure_ascii=False)}"
        elif "archive" in patch:
            reason = patch["archive"].get("reason") if isinstance(patch["archive"], dict) else None
            if not isinstance(reason, str) or not reason.strip():
                raise TaskError("transition_reason_required", "archive 必须提供 reason")
            if metadata["status"] != "closed":
                raise TaskError("archive_requires_closed", "只有 closed Task 可以 archive")
            if not metadata["archived"]:
                metadata["archived"] = True
                metadata["last_transition_reason"] = reason
                changed_fields.append("archived")
                lifecycle_note = f"归档 Task。原因：{reason}"
        elif "unarchive" in patch:
            action = patch["unarchive"]
            reason = action.get("reason") if isinstance(action, dict) else None
            if not isinstance(reason, str) or not reason.strip() or action.get("user_confirmed") is not True:
                raise TaskError("unarchive_confirmation_required", "unarchive 需要 reason 和当前用户明确确认")
            if metadata["archived"]:
                metadata["archived"] = False
                metadata["last_transition_reason"] = reason
                changed_fields.append("archived")
                lifecycle_note = f"取消归档 Task。原因：{reason}"
        if not changed_fields:
            return success({"changed": False, "task_dir": str(record.task_dir)})
        dirty_fields = set(changed_fields)
        if lifecycle_note is not None:
            dirty_fields.add("last_transition_reason")
        for field in dirty_fields:
            if field in metadata:
                record.document.metadata[field] = metadata[field]
            else:
                record.document.metadata.pop(field, None)
        write_record(record)
        warnings: list[dict[str, Any]] = []
        try:
            note = lifecycle_note or f"更新 Task 结构化字段：{', '.join(changed_fields)}。"
            _append_wal(record, actor, note)
        except TaskError as exc:
            warnings.append({"code": "wal_write_failed", "message": exc.message, "committed": True})
        return success(
            {
                "changed": True,
                "committed": True,
                "task_dir": str(record.task_dir),
                "fields": changed_fields,
                "bypassed": bypassed,
            },
            warnings,
        )


OPERATIONS = {
    "task_find": task_find,
    "task_read": task_read,
    "task_create": task_create,
    "task_update": task_update,
    "task_log": task_log,
}


def invoke(operation: str, request: dict[str, Any], *, cwd: str | None = None) -> dict[str, Any]:
    handler = OPERATIONS.get(operation)
    if handler is None:
        raise TaskError("operation_unknown", f"未知操作：{operation}")
    try:
        validate_contract(operation, request)
    except msgspec.ValidationError as exc:
        raise TaskError("request_invalid", "请求不符合 operation contract", {"validation": str(exc)}) from exc
    return handler(request, cwd=cwd)


def version_info() -> dict[str, str]:
    return {"version": VERSION, "protocol_version": PROTOCOL_VERSION, "schema_version": SCHEMA_VERSION}


def uuid7_at(timestamp: datetime) -> UUID:
    raw_milliseconds = timestamp.timestamp() * 1000
    if not 0 <= raw_milliseconds < 1 << 48:
        raise TaskError("timestamp_out_of_range", "时间无法编码为 UUIDv7")
    milliseconds = int(raw_milliseconds)
    value = milliseconds << 80
    value |= 0x7 << 76
    value |= secrets.randbits(12) << 64
    value |= 0b10 << 62
    value |= secrets.randbits(62)
    return UUID(int=value)
