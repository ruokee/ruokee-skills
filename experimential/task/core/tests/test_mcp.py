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
    codex_version = json.loads((package / ".codex-plugin/plugin.json").read_text())["version"]
    module_versions = [
        codex_version.split("+", 1)[0],
        json.loads((package / ".claude-plugin/plugin.json").read_text())["version"],
        json.loads((package / "package.json").read_text())["version"],
    ]
    assert module_versions == [VERSION, VERSION, VERSION]
    assert json.loads((package / "contracts/task-tools.schema.json").read_text()) == schemas()
    plugin_mcp = json.loads((package / ".mcp.json").read_text())["mcpServers"]["task"]
    codex_mcp = json.loads((package / "adapters/codex.mcp.json").read_text())["mcpServers"]["task"]
    assert plugin_mcp["cwd"] == "."
    assert codex_mcp["cwd"] == "."
    assert codex_mcp["command"] == "./bin/task-core"


def test_real_stdio_mcp_lists_and_calls_five_contracts(project: Path) -> None:
    async def scenario() -> None:
        package = Path(__file__).resolve().parents[2] / "package"
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
            cwd=package,
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
            create_tool = next(tool for tool in listed.tools if tool.name == "task_create")
            created_at_schema = create_tool.inputSchema["properties"]["task"]["properties"]["created_at"]
            assert "Only set this when creating a historical Task" in created_at_schema["description"]
            assert "For ordinary Task creation, omit this field" in created_at_schema["description"]
            assert create_tool.description is not None
            assert "Omit created_at for ordinary creation" in create_tool.description
            created = await session.call_tool(
                "task_create",
                {
                    "type": "task",
                    "task": {"name": "MCP Task", "created_at": "2024-02-03T23:05:06.789-05:00"},
                    "user_confirmed": True,
                    "cwd": str(project),
                },
            )
            assert created.structuredContent is not None
            assert created.structuredContent["ok"] is True
            found = await session.call_tool("task_find", {"query": "MCP Task", "cwd": str(project)})
            assert found.structuredContent is not None
            assert len(found.structuredContent["data"]["tasks"]) == 1
            task_id = found.structuredContent["data"]["tasks"][0]["id"]
            read = await session.call_tool(
                "task_read", {"task_ref": task_id, "view": "summary", "cwd": str(project)}
            )
            assert read.structuredContent is not None and read.structuredContent["ok"] is True
            assert read.structuredContent["data"]["metadata"]["created_at"] == "2024-02-03T23:05:06.789-05:00"
            updated = await session.call_tool(
                "task_update",
                {"task_ref": task_id, "patch": {"branch": "mcp/verified"}, "cwd": str(project)},
            )
            assert updated.structuredContent is not None and updated.structuredContent["data"]["changed"] is True
            logged = await session.call_tool(
                "task_log", {"task_ref": task_id, "message": "五工具 smoke 完成。", "cwd": str(project)}
            )
            assert logged.structuredContent is not None and logged.structuredContent["ok"] is True
            task_dir = Path(found.structuredContent["data"]["tasks"][0]["task_dir"])
            assert task_dir.relative_to(project / ".task").parts[:2] == ("2024-02", "03")
            assert "codex:unknown" in next((task_dir / "wal").glob("*.md")).read_text()

    asyncio.run(scenario())
