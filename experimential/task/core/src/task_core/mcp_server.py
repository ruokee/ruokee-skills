import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from task_core import VERSION
from task_core.contracts import schemas
from task_core.errors import TaskError
from task_core.service import invoke

server = Server("task", version=VERSION)

DESCRIPTIONS = {
    "task_find": "Find existing project Tasks without loading full context.",
    "task_read": "Read one Task as metadata, summary, or detailed context.",
    "task_create": (
        "Create one confirmed top-level Task or 1-50 subtasks. "
        "Omit created_at for ordinary creation; set it only for a historical Task with a known timestamp."
    ),
    "task_update": "Apply a semantic Task patch and at most one lifecycle action.",
    "task_log": (
        "Call immediately when a finding, decision, correction, recoverable milestone, verification result, "
        "verified collaboration result, or blocker becomes durable, before later implementation, validation, "
        "handoff, final response, or another work branch. Merge only facts formed in the same semantic event; "
        "do not wait and combine events from different times into one session-end entry."
    ),
}


@server.list_tools()  # type: ignore[untyped-decorator,no-untyped-call]
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name=name, description=DESCRIPTIONS[name], inputSchema=schema) for name, schema in schemas().items()
    ]


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
    try:
        return invoke(name, arguments)
    except TaskError as exc:
        return exc.result()


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    anyio.run(_run)
