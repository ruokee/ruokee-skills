import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from task_core.errors import TaskError


@dataclass(frozen=True, slots=True)
class Config:
    data_dir: Path
    mode: str = "embedded"
    task_root: str = ".task"
    git_policy: str = "ignore"
    creation_policy: str = "strict"
    wal_max_length: int = 2000
    wal_max_entries: int = 20


def xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()


def default_data_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "task"


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    yaml = YAML(typ="safe")
    yaml.allow_duplicate_keys = False
    try:
        value = yaml.load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise TaskError("config_invalid", f"无法解析配置：{path}", {"path": str(path)}) from exc
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TaskError("config_invalid", "Task 配置必须是 YAML mapping", {"path": str(path)})
    return dict(value)


def load_config(project_root: Path | None = None) -> Config:
    merged: dict[str, Any] = {"data_dir": default_data_dir()}
    managed = {item.name for item in fields(Config)}
    for path in [
        xdg_config_home() / "task/config.yaml",
        project_root / ".agents/task.yaml" if project_root else None,
    ]:
        if path is not None:
            merged.update({k: v for k, v in _load_mapping(path).items() if k in managed})

    data_dir = Path(str(merged["data_dir"])).expanduser()
    if not data_dir.is_absolute():
        raise TaskError("config_invalid", "data_dir 展开后必须是绝对路径")
    mode = merged.get("mode", "embedded")
    git_policy = merged.get("git_policy", "ignore")
    creation_policy = merged.get("creation_policy", "strict")
    task_root = merged.get("task_root", ".task")
    wal_max_length = merged.get("wal_max_length", 2000)
    wal_max_entries = merged.get("wal_max_entries", 20)
    if mode not in {"embedded", "detached"}:
        raise TaskError("config_invalid", "mode 必须是 embedded 或 detached")
    if git_policy not in {"ignore", "track", "none"}:
        raise TaskError("config_invalid", "git_policy 必须是 ignore、track 或 none")
    if creation_policy not in {"strict", "permissive"}:
        raise TaskError("config_invalid", "creation_policy 必须是 strict 或 permissive")
    if (
        not isinstance(task_root, str)
        or not task_root
        or Path(task_root).is_absolute()
        or ".." in Path(task_root).parts
    ):
        raise TaskError("config_invalid", "task_root 必须是 project root 内的相对路径")
    if type(wal_max_length) is not int or not 0 <= wal_max_length <= 32000:
        raise TaskError("config_invalid", "wal_max_length 必须是 0..32000 的整数")
    if type(wal_max_entries) is not int or wal_max_entries < 0:
        raise TaskError("config_invalid", "wal_max_entries 必须是非负整数")
    return Config(data_dir, mode, task_root, git_policy, creation_policy, wal_max_length, wal_max_entries)


def load_registry() -> dict[str, str]:
    path = xdg_config_home() / "task/projects.yaml"
    raw = _load_mapping(path)
    projects = raw.get("projects", raw)
    if not isinstance(projects, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in projects.items()
    ):
        raise TaskError("registry_invalid", "projects.yaml 必须保存 path 到 project_slug 的 mapping")
    return dict(projects)


def registry_path() -> Path:
    return xdg_config_home() / "task/projects.yaml"
