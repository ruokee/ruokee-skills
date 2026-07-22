import asyncio
import json
import os
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

BINARY_ENV = "TASK_CORE_BINARY"


def invoke(
    binary: str, project: Path, env: dict[str, str], operation: str, request: dict[str, object]
) -> dict[str, object]:
    process = subprocess.run(
        [binary, "invoke", operation],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        cwd=project,
        env=env,
        check=True,
    )
    return json.loads(process.stdout)


@pytest.mark.skipif(BINARY_ENV not in os.environ, reason="standalone runtime was not selected")
def test_standalone_invoke_concurrency_and_mcp(tmp_path: Path) -> None:
    binary = str(Path(os.environ[BINARY_ENV]).resolve())
    package = Path(__file__).resolve().parents[2] / "package"
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "TASK_HOST": "codex",
    }
    initialized = subprocess.run(
        [binary, "init", "--project-root", str(project)],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    assert json.loads(initialized.stdout)["ok"] is True

    def create(index: int) -> dict[str, object]:
        return invoke(
            binary,
            project,
            env,
            "task_create",
            {"type": "task", "task": {"name": f"Binary {index}"}, "user_confirmed": True},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(create, range(2)))
    leaves = [Path(item["data"]["created"][0]["task_dir"]).name for item in created]
    assert len(set(leaves)) == 2

    async def mcp_scenario() -> None:
        launch_root = tmp_path / "plugin"
        (launch_root / "bin").mkdir(parents=True)
        launcher = launch_root / "bin/task-core"
        launcher.write_text(f"#!/bin/sh\nexec {shlex.quote(binary)} \"$@\"\n")
        launcher.chmod(0o755)
        mcp = json.loads((package / ".mcp.json").read_text())["mcpServers"]["task"]
        mcp_env = {**env}
        mcp_env.pop("CODEX_PLUGIN_ROOT", None)
        mcp_env.pop("CLAUDE_PLUGIN_ROOT", None)
        parameters = StdioServerParameters(
            command=mcp["command"],
            args=mcp["args"],
            cwd=launch_root,
            env=mcp_env,
        )
        async with stdio_client(parameters) as streams, ClientSession(*streams) as session:
            await session.initialize()
            listed = await session.list_tools()
            assert len(listed.tools) == 5
            found = await session.call_tool("task_find", {"query": "Binary", "cwd": str(project)})
            assert found.structuredContent is not None
            assert len(found.structuredContent["data"]["tasks"]) == 2

    asyncio.run(mcp_scenario())
