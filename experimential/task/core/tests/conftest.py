from pathlib import Path

import pytest

from task_core.service import init_project


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path


@pytest.fixture
def project(isolated_env: Path) -> Path:
    root = isolated_env / "project"
    root.mkdir()
    (root / ".git").mkdir()
    result = init_project(project_root=str(root))
    assert result["ok"] is True
    return root
