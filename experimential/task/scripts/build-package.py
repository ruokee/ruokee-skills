#!/usr/bin/env python3
import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
CORE = WORKSPACE / "core"
PACKAGE = WORKSPACE / "package"
TARGET = PACKAGE / "runtime/linux-x86_64/task-core.dist"


def command(*args: str, cwd: Path = CORE) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-checks", action="store_true")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("MVP runtime currently supports Linux x86_64 only")

    command("uv", "lock", "--check")
    if not args.skip_checks:
        command("uv", "run", "--frozen", "ruff", "check", "src", "tests")
        command("uv", "run", "--frozen", "mypy", "src")
        command("uv", "run", "--frozen", "pytest", "-q")
    command("uv", "run", "--frozen", str(WORKSPACE / "scripts/generate-contracts.py"))

    with tempfile.TemporaryDirectory(prefix="task-nuitka-") as temporary:
        build = Path(temporary)
        report = build / "compilation-report.xml"
        command(
            "uv",
            "run",
            "--isolated",
            "--python",
            "3.13",
            "--frozen",
            "python",
            "-m",
            "nuitka",
            "--mode=standalone",
            "--output-filename=task-core.bin",
            f"--output-dir={build}",
            f"--report={report}",
            "--python-flag=-m",
            "src/task_core",
        )
        candidates = list(build.glob("*.dist"))
        if len(candidates) != 1:
            raise SystemExit(f"expected one Nuitka dist directory, got {candidates}")
        staging = PACKAGE / f"runtime/linux-x86_64/.task-core.dist-{os.getpid()}"
        staging.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(candidates[0], staging)
        shutil.copy2(report, staging / "compilation-report.xml")
        version = subprocess.check_output(
            ["uv", "run", "--frozen", "task-core", "--version"], cwd=CORE, text=True
        )
        build_info = {
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "platform": "linux-x86_64",
            "python": "3.13",
            "task": json.loads(version),
        }
        (staging / "BUILD-INFO").write_text(json.dumps(build_info, indent=2) + "\n")
        if TARGET.exists():
            shutil.rmtree(TARGET)
        os.replace(staging, TARGET)
    print(TARGET)


if __name__ == "__main__":
    main()
