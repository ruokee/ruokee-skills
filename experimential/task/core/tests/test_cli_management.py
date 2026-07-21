import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from task_core.errors import TaskError
from task_core.management import check_project, rename_task
from task_core.service import task_create


def create(project: Path, name: str = "Rename Me") -> dict[str, object]:
    return task_create({"type": "task", "task": {"name": name}, "user_confirmed": True}, cwd=str(project))["data"][
        "created"
    ][0]


def test_check_and_rename_gate(project: Path) -> None:
    created = create(project)
    task_dir = Path(str(created["task_dir"]))
    original_partition = task_dir.parent
    task_file = task_dir / "TASK.md"
    task_file.write_text(task_file.read_text() + f"\n自身明确路径：{task_dir}\n")
    note = project / "note.md"
    note.write_text(f"明确路径：{task_dir}\n裸目录：{task_dir.name}\n")
    link = project / "task-link"
    link.symlink_to(task_dir)
    plan = rename_task(str(created["id"]), "Renamed", cwd=str(project), dry_run=True)
    assert plan["data"]["reference_updates"] == 3
    assert plan["data"]["manual_review"]
    with pytest.raises(TaskError) as exc:
        rename_task(str(created["id"]), "Renamed", cwd=str(project))
    assert exc.value.code == "rename_manual_review_required"

    result = rename_task(str(created["id"]), "Renamed", cwd=str(project), allow_unresolved=True)
    assert result["data"]["renamed"] is True
    new_dir = Path(result["data"]["new_path"])
    assert new_dir.is_dir() and not task_dir.exists()
    assert new_dir.parent == original_partition
    assert str(new_dir) in note.read_text()
    assert link.resolve() == new_dir.resolve()
    rewritten = (new_dir / "TASK.md").read_text()
    assert "name: Renamed" in rewritten and str(new_dir) in rewritten
    assert result["data"]["task_id"] == created["id"]
    assert task_core_id(new_dir) == created["id"]
    assert check_project(cwd=str(project))["data"]["healthy"] is True


def task_core_id(task_dir: Path) -> str:
    from task_core.yamlio import load_task_document

    return str(load_task_document(task_dir / "TASK.md").metadata["id"])


def test_rename_same_slug_only_changes_name(project: Path) -> None:
    created = create(project, "Same Slug")
    old_dir = Path(str(created["task_dir"]))
    result = rename_task(str(created["id"]), "Same  Slug", cwd=str(project))
    assert Path(result["data"]["new_path"]) == old_dir
    assert old_dir.is_dir()
    assert "name: Same  Slug" in (old_dir / "TASK.md").read_text()


def test_rename_reports_committed_when_wal_append_fails(project: Path) -> None:
    created = create(project, "Rename with bad WAL")
    task_dir = Path(str(created["task_dir"]))
    next((task_dir / "wal").glob("*.md")).write_bytes(b"\xff")
    result = rename_task(str(created["id"]), "Renamed despite bad WAL", cwd=str(project))
    assert result["ok"] is True and result["data"]["committed"] is True
    assert result["warnings"][0]["code"] == "wal_write_failed"
    assert Path(result["data"]["new_path"]).is_dir()


def test_invoke_domain_error_uses_zero_exit(project: Path) -> None:
    env = os.environ.copy()
    process = subprocess.run(
        [sys.executable, "-m", "task_core", "invoke", "task_read"],
        input=json.dumps({"task_ref": "missing"}),
        text=True,
        capture_output=True,
        cwd=project,
        env=env,
        check=False,
    )
    assert process.returncode == 0
    result = json.loads(process.stdout)
    assert result["ok"] is False and result["error"]["code"] == "task_not_found"


def test_invoke_protocol_error_is_nonzero(project: Path) -> None:
    process = subprocess.run(
        [sys.executable, "-m", "task_core", "invoke", "task_find"],
        input="not json",
        text=True,
        capture_output=True,
        cwd=project,
        check=False,
    )
    assert process.returncode != 0
    assert process.stdout == ""


def test_invoke_rejects_unknown_contract_fields(project: Path) -> None:
    process = subprocess.run(
        [sys.executable, "-m", "task_core", "invoke", "task_find"],
        input=json.dumps({"surprise": True}),
        text=True,
        capture_output=True,
        cwd=project,
        check=False,
    )
    assert process.returncode == 0
    result = json.loads(process.stdout)
    assert result["ok"] is False and result["error"]["code"] == "request_invalid"


def test_git_policy_track_conflict_and_agent_ignore(isolated_env: Path) -> None:
    root = isolated_env / "git-policy"
    root.mkdir()
    subprocess.run(["git", "init", "-q", root], check=True)
    (root / ".gitignore").write_text(".task/\n")
    with pytest.raises(TaskError) as exc:
        from task_core.service import init_project

        init_project(project_root=str(root), git_policy="track")
    assert exc.value.code == "git_policy_conflict"
    assert not (root / ".task").exists()

    agents = root / ".agents"
    agents.mkdir()
    (agents / "task.yaml").write_text("{}\n")
    from task_core.service import init_project

    init_project(project_root=str(root), git_policy="ignore")
    lines = (agents / ".gitignore").read_text().splitlines()
    assert "task.yaml" in lines and ".gitignore" in lines

    tracked = isolated_env / "tracked"
    tracked.mkdir()
    subprocess.run(["git", "init", "-q", tracked], check=True)
    init_project(project_root=str(tracked), git_policy="track")
    assert not (tracked / ".task/.gitignore").exists()
    assert (tracked / ".task/.cache/.gitignore").read_text() == "*\n"
