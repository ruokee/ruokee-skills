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
        choices=("idle", "danger"),
        default="idle",
    )
    result.add_argument("--startup-delay", type=float, default=0.0)
    result.add_argument("--no-bracketed-paste", action="store_true")
    return result


def append_log(path: str | None, value: str) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()


def interactive_loop(
    log: str | None,
    request_bracketed_paste: bool,
) -> int:
    descriptor = sys.stdin.fileno()
    previous = termios.tcgetattr(descriptor)
    paste_start = b"\x1b[200~"
    paste_end = b"\x1b[201~"
    pending = bytearray()
    value = bytearray()
    in_paste = False

    def prompt() -> None:
        sys.stdout.write("› ")
        sys.stdout.flush()

    def submit() -> None:
        text = value.decode("utf-8", errors="replace")
        value.clear()
        append_log(log, text)
        sys.stdout.write(f"\r\nRECEIVED:{text}\r\n")
        prompt()

    try:
        tty.setraw(descriptor)
        if request_bracketed_paste:
            sys.stdout.write("\x1b[?2004h")
        prompt()
        while True:
            chunk = os.read(descriptor, 4096)
            if not chunk:
                return 0
            pending.extend(chunk)
            while pending:
                if (
                    request_bracketed_paste
                    and len(pending) >= len(paste_start)
                    and pending[: len(paste_start)] == paste_start
                ):
                    del pending[: len(paste_start)]
                    in_paste = True
                    continue
                if (
                    request_bracketed_paste
                    and len(pending) >= len(paste_end)
                    and pending[: len(paste_end)] == paste_end
                ):
                    del pending[: len(paste_end)]
                    in_paste = False
                    continue
                pending_bytes = bytes(pending)
                if (
                    (
                        request_bracketed_paste
                        and (
                            (
                                len(pending) < len(paste_start)
                                and paste_start.startswith(pending_bytes)
                            )
                            or (
                                len(pending) < len(paste_end)
                                and paste_end.startswith(pending_bytes)
                            )
                        )
                    )
                ):
                    break
                character = pending.pop(0)
                if character in (10, 13):
                    if in_paste:
                        value.append(10)
                    else:
                        submit()
                else:
                    value.append(character)
    finally:
        if request_bracketed_paste:
            sys.stdout.write("\x1b[?2004l")
            sys.stdout.flush()
        termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)


def main() -> int:
    args, _ = parser().parse_known_args()
    if args.record_argv:
        Path(args.record_argv).write_text(
            json.dumps(sys.argv, ensure_ascii=False), encoding="utf-8"
        )
    time.sleep(args.startup_delay)
    print("MOCK_READY", flush=True)
    if args.mode == "danger":
        print("Allow destructive action? [y/N]", flush=True)
    return interactive_loop(
        args.log,
        not args.no_bracketed_paste,
    )


if __name__ == "__main__":
    raise SystemExit(main())
