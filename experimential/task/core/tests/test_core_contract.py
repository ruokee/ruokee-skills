from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest

from task_core.config import load_config
from task_core.errors import TaskError
from task_core.service import init_project, task_create, task_find, task_log, task_read, task_update
from task_core.store import load_record, write_record
from task_core.yamlio import load_task_document


def create_task(project: Path, name: str = "实现 Task MVP", **fields: object) -> dict[str, object]:
    item = {"name": name, "body": "\n当前目标。\n", **fields}
    result = task_create(
        {"type": "task", "task": item, "user_confirmed": True, "actor": "codex:test"},
        cwd=str(project),
    )
    assert result["ok"] is True
    return result["data"]["created"][0]


def test_embedded_init_ignore_and_strict_creation(project: Path) -> None:
    assert (project / ".task/.gitignore").read_text() == "*\n"
    assert (project / ".task/.cache/.gitignore").read_text() == "*\n"
    assert (project / ".task/.cache/CACHEDIR.TAG").is_file()
    with pytest.raises(TaskError, match="strict") as exc:
        task_create({"type": "task", "task": {"name": "未确认"}}, cwd=str(project))
    assert exc.value.code == "task_creation_confirmation_required"

    created = create_task(project)
    task_dir = Path(str(created["task_dir"]))
    assert task_dir.relative_to(project / ".task").parts[:2] == (task_dir.parent.parent.name, task_dir.parent.name)
    metadata = load_task_document(task_dir / "TASK.md").metadata
    assert metadata["status"] == "open"
    assert metadata["id"] == created["id"]
    assert UUID(metadata["id"]).int >> 80 == int(datetime.fromisoformat(metadata["created_at"]).timestamp() * 1000)
    assert (task_dir / "wal").is_dir()


def test_uninitialized_project_stops_and_permissive_creation_allows_unconfirmed(isolated_env: Path) -> None:
    root = isolated_env / "permissive"
    (root / ".agents").mkdir(parents=True)
    (root / ".git").mkdir()
    with pytest.raises(TaskError) as uninitialized:
        task_create({"type": "task", "task": {"name": "Must not initialize"}}, cwd=str(root))
    assert uninitialized.value.code == "project_not_initialized"
    assert not (root / ".task").exists()

    (root / ".agents/task.yaml").write_text("creation_policy: permissive\n")
    init_project(project_root=str(root))
    created = task_create({"type": "task", "task": {"name": "Permissive Task"}}, cwd=str(root))
    assert created["ok"] is True


def test_embedded_root_and_creation_partitions_do_not_follow_symlinks(isolated_env: Path) -> None:
    root = isolated_env / "symlink-root"
    outside = isolated_env / "outside"
    root.mkdir()
    outside.mkdir()
    (root / ".git").mkdir()
    (root / ".task").symlink_to(outside, target_is_directory=True)
    with pytest.raises(TaskError) as escaped_root:
        init_project(project_root=str(root))
    assert escaped_root.value.code == "task_root_outside_project"

    (root / ".task").unlink()
    init_project(project_root=str(root))
    month = datetime.now().astimezone().strftime("%Y-%m")
    (root / ".task" / month).symlink_to(outside, target_is_directory=True)
    with pytest.raises(TaskError) as escaped_partition:
        create_task(root, "Must stay inside")
    assert escaped_partition.value.code == "task_partition_invalid"
    assert not any(outside.rglob("TASK.md"))


def test_detached_registry_and_discovery(isolated_env: Path) -> None:
    root = isolated_env / "detached-project"
    root.mkdir()
    (root / ".git").mkdir()
    result = init_project(project_root=str(root), mode="detached", project_slug="demo")
    assert result["data"]["task_root"] == str(isolated_env / "data/task/demo")
    registry = (isolated_env / "config/task/projects.yaml").read_text()
    assert str(root) in registry and "demo" in registry
    created = create_task(root, "Detached Task")
    assert Path(str(created["task_dir"])).is_relative_to(isolated_env / "data/task/demo")

    task_root = isolated_env / "data/task/demo"
    task_root.rename(task_root.with_name("demo-missing"))
    with pytest.raises(TaskError) as exc:
        task_find({}, cwd=str(root))
    assert exc.value.code == "task_root_missing"


def test_detached_slug_conflict_is_explicit(isolated_env: Path) -> None:
    first = isolated_env / "first"
    second = isolated_env / "second"
    first.mkdir()
    second.mkdir()
    init_project(project_root=str(first), mode="detached", project_slug="shared")
    with pytest.raises(TaskError) as conflict:
        init_project(project_root=str(second), mode="detached", project_slug="shared")
    assert conflict.value.code == "project_slug_conflict"


def test_project_root_conflict_stops(isolated_env: Path) -> None:
    root = isolated_env / "conflict"
    root.mkdir()
    (root / ".git").mkdir()
    init_project(project_root=str(root), mode="embedded")
    init_project(project_root=str(root), mode="detached", project_slug="conflict-detached")
    with pytest.raises(TaskError) as exc:
        task_find({}, cwd=str(root))
    assert exc.value.code == "root_conflict"


def test_config_precedence_unknown_fields_and_path_rules(isolated_env: Path) -> None:
    root = isolated_env / "configured"
    (root / ".agents").mkdir(parents=True)
    user_config = isolated_env / "config/task/config.yaml"
    user_config.parent.mkdir(parents=True)
    user_config.write_text("task_root: .user-task\ncreation_policy: permissive\nunknown_user: keep-transparent\n")
    (root / ".agents/task.yaml").write_text("task_root: .project-task\nunknown_project: keep-transparent\n")
    config = load_config(root)
    assert config.task_root == ".project-task"
    assert config.creation_policy == "permissive"

    user_config.write_text("data_dir: $HOME/not-expanded\n")
    with pytest.raises(TaskError) as relative:
        load_config(root)
    assert relative.value.code == "config_invalid"

    user_config.write_text("wal_max_entries: true\n")
    with pytest.raises(TaskError) as boolean:
        load_config(root)
    assert boolean.value.code == "config_invalid"


def test_find_read_log_and_yaml_roundtrip(project: Path) -> None:
    created = create_task(project, branch="feat/task")
    task_dir = Path(str(created["task_dir"]))
    task_file = task_dir / "TASK.md"
    original = task_file.read_text()
    task_file.write_text(
        original.replace(
            "schema_version: '2026-07-21'",
            'schema_version: "2026-07-21" # keep\nunknown: &v "yes"\nalias: *v',
        )
    )

    found = task_find({"branch": "feat/task"}, cwd=str(project))
    assert [item["id"] for item in found["data"]["tasks"]] == [created["id"]]
    task_log(
        {"task_ref": str(created["id"]), "message": "完成发现。", "extra_body": "第二段。", "actor": "pi:test"},
        cwd=str(project),
    )
    updated = task_update(
        {"task_ref": str(created["id"]), "patch": {"extra": {"set": {"owner": "Ruokee"}}}},
        cwd=str(project),
    )
    assert updated["data"]["changed"] is True
    rewritten = task_file.read_text()
    assert "# keep" in rewritten and 'unknown: &v "yes"' in rewritten and "alias: *v" in rewritten
    assert rewritten.endswith("\n当前目标。\n")

    summary = task_read({"task_ref": str(created["id"]), "view": "summary"}, cwd=str(project))
    detailed = task_read({"task_ref": str(created["id"]), "view": "detailed"}, cwd=str(project))
    metadata = task_read({"task_ref": str(created["id"]), "view": "metadata"}, cwd=str(project))
    assert summary["data"]["body"] == "\n当前目标。\n"
    assert len(detailed["data"]["wal"]) >= 3
    assert "body" not in metadata["data"] and "wal" not in metadata["data"]


def test_all_supported_references_and_uuid_prefix_rejection(project: Path) -> None:
    created = create_task(project, "Reference Target", branch="ref/target")
    task_dir = Path(str(created["task_dir"]))
    relative = str(task_dir.relative_to(project))
    for task_ref in (created["id"], str(created["id"]).upper(), "Reference Target", task_dir.name, relative):
        assert (
            task_read({"task_ref": task_ref, "view": "metadata"}, cwd=str(project))["data"]["metadata"]["id"]
            == created["id"]
        )
    assert task_find({"branch": "ref/target"}, cwd=str(project))["data"]["tasks"][0]["id"] == created["id"]
    with pytest.raises(TaskError) as exc:
        task_read({"task_ref": str(created["id"])[:12]}, cwd=str(project))
    assert exc.value.code == "task_not_found"


def test_subtasks_relations_and_lifecycle(project: Path) -> None:
    parent = create_task(project, "Parent")
    sibling = create_task(project, "Dependency")
    children = task_create(
        {
            "type": "subtasks",
            "parent_ref": parent["id"],
            "subtasks": [{"name": "Child A"}, {"name": "Child B"}],
            "actor": "codex:test",
        },
        cwd=str(project),
    )["data"]["created"]
    assert all(Path(item["task_dir"]).parent.name == "subtasks" for item in children)

    task_update(
        {
            "task_ref": parent["id"],
            "patch": {"depends_on": {"add": [sibling["id"]], "remove": []}},
        },
        cwd=str(project),
    )
    with pytest.raises(TaskError) as blocked:
        task_update(
            {"task_ref": parent["id"], "patch": {"transition": {"status": "closed", "reason": "完成"}}},
            cwd=str(project),
        )
    assert blocked.value.code == "task_close_blocked"

    forced = task_update(
        {
            "task_ref": parent["id"],
            "patch": {"transition": {"status": "closed", "reason": "用户要求", "force": True}},
        },
        cwd=str(project),
    )
    assert forced["data"]["bypassed"]
    ordinary_ids = {item["id"] for item in task_find({}, cwd=str(project))["data"]["tasks"]}
    assert children[0]["id"] not in ordinary_ids
    found_child = task_find({"query": children[0]["id"]}, cwd=str(project))
    assert found_child["data"]["tasks"][0]["id"] == children[0]["id"]
    parent_detail = task_read({"task_ref": parent["id"], "view": "detailed"}, cwd=str(project))
    assert any("强制绕过" in entry["body"] for entry in parent_detail["data"]["wal"])
    with pytest.raises(TaskError):
        task_update(
            {"task_ref": parent["id"], "patch": {"archive": {"reason": "归档"}, "unarchive": {"reason": "撤销"}}},
            cwd=str(project),
        )
    task_update({"task_ref": parent["id"], "patch": {"archive": {"reason": "完成"}}}, cwd=str(project))
    with pytest.raises(TaskError) as archived:
        task_update(
            {"task_ref": parent["id"], "patch": {"transition": {"status": "open", "reason": "继续"}}},
            cwd=str(project),
        )
    assert archived.value.code == "archived_task_cannot_reopen"

    task_log({"task_ref": parent["id"], "message": "归档后补充事实。"}, cwd=str(project))
    with pytest.raises(TaskError) as force_non_close:
        task_update(
            {
                "task_ref": sibling["id"],
                "patch": {"transition": {"status": "paused", "reason": "暂停", "force": True}},
            },
            cwd=str(project),
        )
    assert force_non_close.value.code == "request_invalid"


def test_wal_budgets(project: Path) -> None:
    created = create_task(project, "WAL Budget")
    for index in range(6):
        task_log(
            {"task_ref": created["id"], "message": f"记录 {index}", "extra_body": "x" * 80},
            cwd=str(project),
        )
    by_entries = task_read(
        {"task_ref": created["id"], "view": "detailed", "wal_max_entries": 2, "wal_max_length": 32000},
        cwd=str(project),
    )
    assert len(by_entries["data"]["wal"]) == 2 and by_entries["data"]["wal_truncated"] is True
    by_chars = task_read(
        {"task_ref": created["id"], "view": "detailed", "wal_max_entries": None, "wal_max_length": 80},
        cwd=str(project),
    )
    assert len(by_chars["data"]["wal"]) == 1
    assert by_chars["data"]["wal"][0]["truncated"] is True


def test_cross_day_wal_views_and_malformed_warnings(project: Path) -> None:
    created = create_task(project, "Cross-day WAL")
    wal_dir = Path(str(created["task_dir"])) / "wal"
    (wal_dir / "2026-07-20.md").write_text(
        "人工前缀。\n\n## 2026-07-20T23:59:00.000+08:00 · pi:test\n\n第一段。\n\n第二段。\n"
    )
    (wal_dir / "offsets.md").write_text(
        "## 2026-07-20T23:30:00.000-10:00 · pi:later\n\n较晚。\n\n"
        "## 2026-07-21T01:00:00.000+08:00 · pi:earlier\n\n较早。\n"
    )
    metadata = task_read({"task_ref": created["id"], "view": "metadata"}, cwd=str(project))
    summary = task_read({"task_ref": created["id"], "view": "summary"}, cwd=str(project))
    detailed = task_read({"task_ref": created["id"], "view": "detailed"}, cwd=str(project))
    assert "wal" not in metadata["data"]
    assert summary["data"]["wal"][0]["body"] == "第一段。"
    assert detailed["data"]["wal"][0]["body"] == "第一段。\n\n第二段。"
    actors = [item["actor"] for item in detailed["data"]["wal"]]
    assert actors.index("pi:earlier") < actors.index("pi:later")
    assert any(item["code"] == "wal_unparsed_text" for item in detailed["warnings"])
    tiny = task_read({"task_ref": created["id"], "view": "detailed", "wal_max_length": 1}, cwd=str(project))
    assert tiny["data"]["wal"] == [] and tiny["data"]["wal_truncated"] is True


def test_wal_append_rejects_non_utf8_and_symlink(project: Path) -> None:
    created = create_task(project, "WAL safety")
    wal_path = next((Path(str(created["task_dir"])) / "wal").glob("*.md"))
    wal_path.write_bytes(b"\xff")
    committed = task_update({"task_ref": created["id"], "patch": {"branch": "committed-before-wal"}}, cwd=str(project))
    assert committed["ok"] is True and committed["data"]["committed"] is True
    assert committed["warnings"][0]["code"] == "wal_write_failed"
    with pytest.raises(TaskError) as invalid_utf8:
        task_log({"task_ref": created["id"], "message": "不能追加"}, cwd=str(project))
    assert invalid_utf8.value.code == "wal_invalid_utf8"

    target = wal_path.with_name("external.md")
    target.write_text("external\n")
    wal_path.unlink()
    wal_path.symlink_to(target)
    with pytest.raises(TaskError) as symlink:
        task_log({"task_ref": created["id"], "message": "不能覆盖 symlink"}, cwd=str(project))
    assert symlink.value.code == "wal_not_regular_file"


def test_concurrent_top_level_creation_allocates_unique_slots(project: Path) -> None:
    def create(index: int) -> dict[str, object]:
        return create_task(project, f"并发 {index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(create, range(2)))
    leaves = [Path(str(item["task_dir"])).name for item in created]
    assert len(set(leaves)) == 2
    assert {item.split("--", 1)[0] for item in leaves} == {"01", "02"}


def test_different_top_level_trees_update_in_parallel(project: Path) -> None:
    created = [create_task(project, f"Parallel {index}") for index in range(2)]

    def update(index: int) -> dict[str, object]:
        return task_update(
            {"task_ref": created[index]["id"], "patch": {"branch": f"parallel/{index}"}},
            cwd=str(project),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, range(2)))
    assert all(result["data"]["changed"] is True for result in results)
    assert [
        task_read({"task_ref": item["id"], "view": "metadata"}, cwd=str(project))["data"]["metadata"]["branch"]
        for item in created
    ] == ["parallel/0", "parallel/1"]


def test_ambiguous_name_stops(project: Path) -> None:
    first = create_task(project, "Same")
    second = create_task(project, "Other")
    second_path = Path(str(second["task_dir"])) / "TASK.md"
    second_path.write_text(second_path.read_text().replace("name: Other", "name: Same"))
    with pytest.raises(TaskError) as exc:
        task_read({"task_ref": "Same"}, cwd=str(project))
    assert exc.value.code == "task_ref_ambiguous"
    assert len(exc.value.details["candidates"]) == 2
    assert first["id"] != second["id"]


def test_duplicate_uuid_blocks_modification_even_when_name_is_unique(project: Path) -> None:
    first = create_task(project, "First identity")
    second = create_task(project, "Second identity")
    second_path = Path(str(second["task_dir"])) / "TASK.md"
    second_path.write_text(second_path.read_text().replace(str(second["id"]), str(first["id"]), 1))
    with pytest.raises(TaskError) as exc:
        task_update({"task_ref": "First identity", "patch": {"branch": "unsafe"}}, cwd=str(project))
    assert exc.value.code == "task_ref_ambiguous"


def test_relation_ids_must_be_full_uuid7(project: Path) -> None:
    created = create_task(project, "Bad relation")
    task_file = Path(str(created["task_dir"])) / "TASK.md"
    task_file.write_text(task_file.read_text().replace("depends_on: []", "depends_on: [not-a-uuid]"))
    result = task_read({"task_ref": str(task_file.parent), "view": "metadata"}, cwd=str(project))
    assert result["data"]["managed_valid"] is False
    assert any(item["field"] == "depends_on" for item in result["data"]["validation_errors"])
    clean = create_task(project, "Invalid relation request")
    with pytest.raises(TaskError) as update:
        task_update({"task_ref": clean["id"], "patch": {"related_to": {"add": ["not-a-uuid"]}}}, cwd=str(project))
    assert update.value.code == "request_invalid"


def test_handwritten_missing_relations_warn_but_only_block_close(project: Path) -> None:
    created = create_task(project, "Missing relations")
    missing = "019f849f-1ab6-715d-a305-b4abe2afc4bf"
    task_file = Path(str(created["task_dir"])) / "TASK.md"
    task_file.write_text(
        task_file.read_text()
        .replace("depends_on: []", f"depends_on: [{missing}]")
        .replace("related_to: []", f"related_to: [{missing}]")
    )
    result = task_read({"task_ref": created["id"], "view": "metadata"}, cwd=str(project))
    assert result["data"]["managed_valid"] is True
    assert {item["code"] for item in result["warnings"]} >= {"dependency_missing", "related_missing"}
    assert (
        task_update({"task_ref": created["id"], "patch": {"branch": "still-editable"}}, cwd=str(project))["data"][
            "changed"
        ]
        is True
    )
    with pytest.raises(TaskError) as blocked:
        task_update(
            {"task_ref": created["id"], "patch": {"transition": {"status": "closed", "reason": "完成"}}},
            cwd=str(project),
        )
    assert blocked.value.code == "task_close_blocked"


def test_relation_self_and_dependency_cycle_are_rejected(project: Path) -> None:
    first = create_task(project, "Cycle first")
    second = create_task(project, "Cycle second")
    with pytest.raises(TaskError) as self_relation:
        task_update({"task_ref": first["id"], "patch": {"related_to": {"add": [first["id"]]}}}, cwd=str(project))
    assert self_relation.value.code == "relation_self"
    task_update({"task_ref": first["id"], "patch": {"depends_on": {"add": [second["id"]]}}}, cwd=str(project))
    with pytest.raises(TaskError) as cycle:
        task_update({"task_ref": second["id"], "patch": {"depends_on": {"add": [first["id"]]}}}, cwd=str(project))
    assert cycle.value.code == "dependency_cycle"

    third = create_task(project, "Combined close")
    with pytest.raises(TaskError) as combined:
        task_update(
            {
                "task_ref": third["id"],
                "patch": {
                    "depends_on": {"add": [first["id"]]},
                    "transition": {"status": "closed", "reason": "尝试同批关闭"},
                },
            },
            cwd=str(project),
        )
    assert combined.value.code == "task_close_blocked"


def test_visible_external_write_race_is_rejected(project: Path) -> None:
    created = create_task(project, "Race")
    task_dir = Path(str(created["task_dir"]))
    record = load_record(task_dir)
    assert record.document is not None
    record.document.metadata["branch"] = "stale"
    task_file = task_dir / "TASK.md"
    task_file.write_text(task_file.read_text() + "external\n")
    with pytest.raises(TaskError) as exc:
        write_record(record)
    assert exc.value.code == "external_write_race"


def test_explicit_path_cannot_escape_project_task_root(project: Path, isolated_env: Path) -> None:
    other = isolated_env / "other"
    other.mkdir()
    (other / ".git").mkdir()
    init_project(project_root=str(other))
    outside = create_task(other, "Other project")
    with pytest.raises(TaskError) as exc:
        task_read({"task_ref": outside["task_dir"]}, cwd=str(project))
    assert exc.value.code == "task_cross_project"


def test_safe_yaml_tags_are_allowed_and_custom_tags_rejected(project: Path) -> None:
    safe = create_task(project, "Safe tag")
    safe_file = Path(str(safe["task_dir"])) / "TASK.md"
    safe_file.write_text(safe_file.read_text().replace("name: Safe tag", "name: !!str Safe tag"))
    assert task_read({"task_ref": str(safe_file.parent)}, cwd=str(project))["data"]["managed_valid"] is True

    unsafe = create_task(project, "Unsafe tag")
    unsafe_file = Path(str(unsafe["task_dir"])) / "TASK.md"
    unsafe_file.write_text(unsafe_file.read_text().replace("name: Unsafe tag", "name: !custom Unsafe tag"))
    result = task_read({"task_ref": str(unsafe_file.parent)}, cwd=str(project))
    assert result["data"]["managed_valid"] is False

    deceptive = create_task(project, "Deceptive tag")
    deceptive_file = Path(str(deceptive["task_dir"])) / "TASK.md"
    deceptive_file.write_text(
        deceptive_file.read_text().replace("name: Deceptive tag", "name: !<tag:yaml.org,2002:evil> Deceptive tag")
    )
    assert task_read({"task_ref": str(deceptive_file.parent)}, cwd=str(project))["data"]["managed_valid"] is False

    duplicate = create_task(project, "Duplicate key")
    duplicate_file = Path(str(duplicate["task_dir"])) / "TASK.md"
    duplicate_file.write_text(
        duplicate_file.read_text().replace("name: Duplicate key", "name: Duplicate key\nname: Duplicate again")
    )
    assert task_read({"task_ref": str(duplicate_file.parent)}, cwd=str(project))["data"]["managed_valid"] is False


def test_noncanonical_move_warns_without_blocking_operations(project: Path) -> None:
    created = create_task(project, "Moved manually")
    old_dir = Path(str(created["task_dir"]))
    new_dir = project / ".task/manual" / old_dir.name
    new_dir.parent.mkdir()
    old_dir.rename(new_dir)
    result = task_read({"task_ref": created["id"], "view": "metadata"}, cwd=str(project))
    assert any(item["code"] == "noncanonical_task_path" for item in result["warnings"])
    assert (
        task_update({"task_ref": created["id"], "patch": {"branch": "after/manual-move"}}, cwd=str(project))["data"][
            "changed"
        ]
        is True
    )
    assert task_log({"task_ref": created["id"], "message": "移动后仍可记录。"}, cwd=str(project))["ok"] is True
