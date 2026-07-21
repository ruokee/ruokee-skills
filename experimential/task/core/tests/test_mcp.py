import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from task_core import VERSION
from task_core.contracts import schemas


def test_package_versions_and_generated_contracts_are_lockstep() -> None:
    package = Path(__file__).resolve().parents[2] / "package"
    versions = [
        json.loads((package / ".codex-plugin/plugin.json").read_text())["version"],
        json.loads((package / ".claude-plugin/plugin.json").read_text())["version"],
        json.loads((package / "package.json").read_text())["version"],
    ]
    assert versions == [VERSION, VERSION, VERSION]
    assert json.loads((package / "contracts/task-tools.schema.json").read_text()) == schemas()


def test_real_stdio_mcp_lists_and_calls_five_contracts(project: Path) -> None:
    async def scenario() -> None:
        env = {
            "HOME": os.environ["HOME"],
            "PATH": os.environ["PATH"],
            "XDG_CONFIG_HOME": os.environ["XDG_CONFIG_HOME"],
            "XDG_DATA_HOME": os.environ["XDG_DATA_HOME"],
            "TASK_HOST": "codex",
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "task_core", "mcp"],
            cwd=project,
            env=env,
        )
        async with stdio_client(parameters) as streams, ClientSession(*streams) as session:
            await session.initialize()
            listed = await session.list_tools()
            assert {tool.name for tool in listed.tools} == {
                "task_find",
                "task_read",
                "task_create",
                "task_update",
                "task_log",
            }
            assert all(tool.inputSchema for tool in listed.tools)
            assert all(tool.inputSchema.get("type") == "object" for tool in listed.tools)
            assert all("$defs" not in tool.inputSchema for tool in listed.tools)
            created = await session.call_tool(
                "task_create",
                {
                    "type": "task",
                    "task": {"name": "MCP Task"},
                    "user_confirmed": True,
                },
            )
            assert created.structuredContent is not None
            assert created.structuredContent["ok"] is True
            found = await session.call_tool("task_find", {"query": "MCP Task"})
            assert found.structuredContent is not None
            assert len(found.structuredContent["data"]["tasks"]) == 1
            task_id = found.structuredContent["data"]["tasks"][0]["id"]
            read = await session.call_tool("task_read", {"task_ref": task_id, "view": "summary"})
            assert read.structuredContent is not None and read.structuredContent["ok"] is True
            updated = await session.call_tool("task_update", {"task_ref": task_id, "patch": {"branch": "mcp/verified"}})
            assert updated.structuredContent is not None and updated.structuredContent["data"]["changed"] is True
            logged = await session.call_tool("task_log", {"task_ref": task_id, "message": "五工具 smoke 完成。"})
            assert logged.structuredContent is not None and logged.structuredContent["ok"] is True
            task_dir = Path(found.structuredContent["data"]["tasks"][0]["task_dir"])
            assert "codex:unknown" in next((task_dir / "wal").glob("*.md")).read_text()

    asyncio.run(scenario())
