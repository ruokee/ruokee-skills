import os
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from urllib.parse import quote

from task_core.errors import TaskError, success
from task_core.service import _append_wal, normalize_actor
from task_core.store import (
    ProjectContext,
    atomic_write,
    canonical,
    directory_lock,
    discover_project,
    discover_tasks,
    require_unique_record,
    require_valid,
    slugify,
    validate_name,
    write_record,
)


def check_project(*, cwd: str | None = None) -> dict[str, Any]:
    context = discover_project(Path(cwd or os.getcwd()))
    records = discover_tasks(context, penetrate_closed=True)
    id_paths: dict[str, list[str]] = {}
    invalid: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for record in records:
        if record.id:
            id_paths.setdefault(record.id, []).append(str(record.task_dir))
        if not record.valid:
            invalid.append({"task_dir": str(record.task_dir), "errors": record.errors})
        warnings.extend({**warning, "task_dir": str(record.task_dir)} for warning in record.warnings)
    duplicates = {key: paths for key, paths in id_paths.items() if len(paths) > 1}
    issues: list[dict[str, Any]] = []
    if duplicates:
        issues.append({"code": "duplicate_task_id", "tasks": duplicates})
    if invalid:
        issues.append({"code": "invalid_task_candidates", "tasks": invalid})
    staging = [str(path) for path in context.task_root.rglob(".*.tmp") if path.is_file() and not path.is_symlink()]
    if staging:
        issues.append({"code": "staging_files_found", "paths": staging})
    return success(
        {
            "healthy": not issues,
            "project_root": str(context.project_root),
            "task_root": str(context.task_root),
            "task_count": len(records),
            "issues": issues,
        },
        warnings,
    )


def _rename_scan(context: ProjectContext, old_dir: Path, new_dir: Path) -> dict[str, Any]:
    replacements: list[dict[str, Any]] = []
    manual_review: list[dict[str, Any]] = []
    old_abs = str(canonical(old_dir))
    new_abs = str(canonical(new_dir))
    old_relative = (
        str(canonical(old_dir).relative_to(context.project_root))
        if old_dir.is_relative_to(context.project_root)
        else None
    )
    new_relative = (
        str(canonical(new_dir).relative_to(context.project_root))
        if new_dir.is_relative_to(context.project_root)
        else None
    )
    roots = {context.project_root, context.task_root}
    visited: set[Path] = set()
    for root in roots:
        for path in root.rglob("*"):
            if path in visited or ".git" in path.parts or ".cache" in path.parts:
                continue
            visited.add(path)
            if path.is_symlink():
                raw = os.readlink(path)
                resolved = canonical(path.parent / raw) if not Path(raw).is_absolute() else canonical(Path(raw))
                if resolved == canonical(old_dir) or canonical(old_dir) in resolved.parents:
                    suffix = resolved.relative_to(canonical(old_dir))
                    target = canonical(new_dir) / suffix
                    replacements.append({"kind": "symlink", "path": str(path), "old": raw, "new": str(target)})
                elif old_dir.name in raw:
                    manual_review.append({"kind": "symlink", "path": str(path), "value": raw})
                continue
            if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml", ".json", ".toml"}:
                continue
            if "wal" in path.relative_to(context.task_root).parts if path.is_relative_to(context.task_root) else False:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            pairs = [(old_abs, new_abs)]
            if old_relative and new_relative:
                pairs.append((old_relative, new_relative))
            changed = text
            for old, new in pairs:
                changed = changed.replace(old, new)
            if changed != text:
                replacements.append({"kind": "text", "path": str(path), "old": text, "new": changed, "pairs": pairs})
            encoded_values = {quote(old_abs), quote(old_abs, safe="")}
            if old_relative:
                encoded_values.update({quote(old_relative), quote(old_relative, safe="")})
            if any(value in changed for value in encoded_values):
                manual_review.append({"kind": "encoded_path", "path": str(path), "value": old_dir.name})
            if old_dir.name in changed and path != old_dir / "TASK.md":
                manual_review.append({"kind": "text", "path": str(path), "value": old_dir.name})
    return {"replacements": replacements, "manual_review": manual_review}


def rename_task(
    task_ref: str,
    name: str,
    *,
    cwd: str | None = None,
    actor: str | None = None,
    dry_run: bool = False,
    allow_unresolved: bool = False,
) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    context = discover_project(Path(cwd or os.getcwd()))
    record = require_unique_record(context, task_ref)
    require_valid(record)
    normalized = validate_name(name)
    prefix = record.task_dir.name.split("--", 1)[0]
    new_dir = record.task_dir.with_name(f"{prefix}--{slugify(normalized)}")
    old_name = str(record.metadata["name"])
    if canonical(new_dir) != canonical(record.task_dir) and os.path.lexists(new_dir):
        raise TaskError("directory_exists", "rename 目标目录已存在", {"path": str(new_dir)})
    scan = _rename_scan(context, record.task_dir, new_dir)
    plan = {
        "task_id": record.id,
        "old_name": old_name,
        "new_name": normalized,
        "old_path": str(record.task_dir),
        "new_path": str(new_dir),
        "reference_updates": len(scan["replacements"]),
        "manual_review": scan["manual_review"],
    }
    if dry_run:
        return success({"dry_run": True, **plan})
    if scan["manual_review"] and not allow_unresolved:
        raise TaskError("rename_manual_review_required", "存在无法唯一判断的路径引用", plan)
    with ExitStack() as locks:
        locks.enter_context(directory_lock(context.project_root))
        top_dirs = sorted(
            item.task_dir
            for item in discover_tasks(context, penetrate_closed=True)
            if item.valid and item.parent_id is None
        )
        for top_dir in top_dirs:
            locks.enter_context(directory_lock(top_dir))
        record = require_unique_record(context, task_ref)
        require_valid(record)
        assert record.document is not None
        new_dir = record.task_dir.with_name(f"{record.task_dir.name.split('--', 1)[0]}--{slugify(normalized)}")
        if canonical(new_dir) != canonical(record.task_dir) and os.path.lexists(new_dir):
            raise TaskError("directory_exists", "rename 目标目录已存在", {"path": str(new_dir)})
        scan = _rename_scan(context, record.task_dir, new_dir)
        if scan["manual_review"] and not allow_unresolved:
            raise TaskError("rename_manual_review_required", "锁内重检发现无法唯一判断的路径引用", plan)
        record.document.metadata["name"] = normalized
        write_record(record)
        if canonical(new_dir) != canonical(record.task_dir):
            os.replace(record.task_dir, new_dir)
        for item in scan["replacements"]:
            path = Path(item["path"])
            if path == record.task_dir or record.task_dir in path.parents:
                path = new_dir / path.relative_to(record.task_dir)
            if item["kind"] == "text":
                if path == new_dir / "TASK.md":
                    current = path.read_text(encoding="utf-8")
                    changed = current
                    for old, new in item["pairs"]:
                        changed = changed.replace(old, new)
                    atomic_write(path, changed.encode(), expected=current.encode())
                else:
                    atomic_write(path, item["new"].encode(), expected=item["old"].encode())
            else:
                if not path.is_symlink() or os.readlink(path) != item["old"]:
                    raise TaskError("external_write_race", "symlink 在 rename 前被外部修改", {"path": str(path)})
                path.unlink()
                path.symlink_to(item["new"])
        renamed = require_unique_record(context, record.id)
        try:
            _append_wal(
                renamed,
                normalize_actor(actor),
                f"Task 更名：{old_name} → {normalized}。",
                f"旧路径：{record.task_dir}\n新路径：{new_dir}\n更新引用：{len(scan['replacements'])}\n待人工检查：{len(scan['manual_review'])}",
            )
        except TaskError as exc:
            warnings.append({"code": "wal_write_failed", "message": exc.message, "committed": True})
        plan = {
            "task_id": record.id,
            "old_name": old_name,
            "new_name": normalized,
            "old_path": str(record.task_dir),
            "new_path": str(new_dir),
            "reference_updates": len(scan["replacements"]),
            "manual_review": scan["manual_review"],
        }
    return success({"renamed": True, "committed": True, **plan}, warnings)
