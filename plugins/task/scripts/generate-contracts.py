#!/usr/bin/env python3
import json
from pathlib import Path

from task_core.contracts import schemas

WORKSPACE = Path(__file__).resolve().parents[1]
OUTPUT = WORKSPACE / "package/contracts/task-tools.schema.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(schemas(), ensure_ascii=False, indent=2) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
