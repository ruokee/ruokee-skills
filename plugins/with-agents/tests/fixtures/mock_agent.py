#!/usr/bin/env python3
"""Small interactive fixture for isolated with-agents tmux tests."""

import argparse
import json
import os
from pathlib import Path
import sys
import termios
import time
import tty


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--log")
    result.add_argument("--record-argv")
    result.add_argument(
        "--mode",
        choices=("idle", "busy", "danger", "codex-background"),
        default="idle",
    )
    result.add_argument("--startup-delay", type=float, default=0.0)
    result.add_argument("--request-extended-keys", action="store_true")
    result.add_argument("--version", action="store_true")
    return result


def append_log(path: str | None, value: str) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()


def interactive_loop(log: str | None, mode: str, request_extended_keys: bool) -> int:
    descriptor = sys.stdin.fileno()
    previous = termios.tcgetattr(descriptor)
    paste_start = b"\x1b[200~"
    paste_end = b"\x1b[201~"
    meta_enter_csi_u = b"\x1b[13;3u"
    pending = bytearray()
    value = bytearray()
    in_paste = False

    def prompt() -> None:
        if mode == "codex-background":
            sys.stdout.write(
                "\x1b[1;38;5;250m›\x1b[0m "
                "\x1b[48;2;32;35;42m\x1b[2mFind and fix a bug\x1b[0m"
            )
        else:
            sys.stdout.write("› ")
        sys.stdout.flush()

    def submit(prefix: str = "RECEIVED") -> None:
        text = value.decode("utf-8", errors="replace")
        value.clear()
        append_log(log, text)
        sys.stdout.write(f"\r\n{prefix}:{text}\r\n")
        prompt()

    try:
        tty.setraw(descriptor)
        sys.stdout.write("\x1b[?2004h")
        if request_extended_keys:
            sys.stdout.write("\x1b[>4;2m")
        prompt()
        while True:
            chunk = os.read(descriptor, 4096)
            if not chunk:
                return 0
            pending.extend(chunk)
            while pending:
                if (
                    len(pending) >= len(paste_start)
                    and pending[: len(paste_start)] == paste_start
                ):
                    del pending[: len(paste_start)]
                    in_paste = True
                    continue
                if (
                    len(pending) >= len(paste_end)
                    and pending[: len(paste_end)] == paste_end
                ):
                    del pending[: len(paste_end)]
                    in_paste = False
                    continue
                if (
                    len(pending) >= len(meta_enter_csi_u)
                    and pending[: len(meta_enter_csi_u)] == meta_enter_csi_u
                ):
                    del pending[: len(meta_enter_csi_u)]
                    if mode == "busy" and not in_paste:
                        submit("QUEUED")
                    else:
                        value.extend(meta_enter_csi_u)
                    continue
                pending_bytes = bytes(pending)
                if (
                    (
                        len(pending) < len(paste_start)
                        and paste_start.startswith(pending_bytes)
                    )
                    or (
                        len(pending) < len(paste_end)
                        and paste_end.startswith(pending_bytes)
                    )
                    or (
                        len(pending) < len(meta_enter_csi_u)
                        and meta_enter_csi_u.startswith(pending_bytes)
                    )
                ):
                    break
                character = pending.pop(0)
                if character in (10, 13):
                    if in_paste:
                        value.append(10)
                    else:
                        submit()
                elif character == 9 and mode == "busy" and not in_paste:
                    submit("QUEUED")
                else:
                    value.append(character)
    finally:
        sys.stdout.write("\x1b[?2004l")
        sys.stdout.flush()
        termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)


def main() -> int:
    args, unknown = parser().parse_known_args()
    executable = Path(sys.argv[0]).name
    if args.version:
        if executable == "codex":
            print(os.environ.get("MOCK_AGENT_VERSION", "codex-cli 0.145.0"))
        elif executable == "pi":
            print("pi 0.80.6")
        else:
            print("mock-agent 1.0.0")
        return 0
    if args.record_argv:
        Path(args.record_argv).write_text(
            json.dumps(sys.argv, ensure_ascii=False), encoding="utf-8"
        )
    time.sleep(args.startup_delay)
    print("MOCK_READY", flush=True)
    if args.mode == "busy":
        print("esc to interrupt", flush=True)
    elif args.mode == "danger":
        print("Allow destructive action? [y/N]", flush=True)
    return interactive_loop(args.log, args.mode, args.request_extended_keys)


if __name__ == "__main__":
    raise SystemExit(main())
