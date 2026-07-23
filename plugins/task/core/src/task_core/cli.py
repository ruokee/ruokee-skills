import argparse
import json
import sys
from typing import Any

from task_core.errors import TaskError
from task_core.management import check_project, rename_task
from task_core.service import init_project, invoke, version_info


def _json_input() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("stdin 必须是 JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError("stdin 必须是 JSON object")
    return value


def _print(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="task-core")
    root.add_argument("--version", action="store_true")
    commands = root.add_subparsers(dest="command")
    invoke_parser = commands.add_parser("invoke", help="stdin JSON → stdout JSON")
    invoke_parser.add_argument(
        "operation", choices=["task_find", "task_read", "task_create", "task_update", "task_log"]
    )
    commands.add_parser("mcp", help="run stdio MCP server")
    init = commands.add_parser("init")
    init.add_argument("--project-root")
    init.add_argument("--mode", choices=["embedded", "detached"])
    init.add_argument("--git-policy", choices=["ignore", "track", "none"])
    init.add_argument("--project-slug")
    commands.add_parser("check")
    rename = commands.add_parser("rename")
    rename.add_argument("task_ref")
    rename.add_argument("name")
    rename.add_argument("--actor")
    rename.add_argument("--dry-run", action="store_true")
    rename.add_argument("--allow-unresolved", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.version:
        _print(version_info())
        return 0
    try:
        if args.command == "invoke":
            # Domain failures deliberately use exit 0; malformed transport uses exit 2 below.
            try:
                request = _json_input()
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            try:
                result = invoke(args.operation, request)
            except TaskError as exc:
                result = exc.result()
            _print(result)
            return 0
        if args.command == "mcp":
            from task_core.mcp_server import run

            run()
            return 0
        if args.command == "init":
            _print(
                init_project(
                    project_root=args.project_root,
                    mode=args.mode,
                    git_policy=args.git_policy,
                    project_slug=args.project_slug,
                )
            )
            return 0
        if args.command == "check":
            _print(check_project())
            return 0
        if args.command == "rename":
            _print(
                rename_task(
                    args.task_ref,
                    args.name,
                    actor=args.actor,
                    dry_run=args.dry_run,
                    allow_unresolved=args.allow_unresolved,
                )
            )
            return 0
        parser().print_help()
        return 0
    except TaskError as exc:
        _print(exc.result())
        return 1
