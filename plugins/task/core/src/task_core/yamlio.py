import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.tokens import TagToken

from task_core.errors import TaskError

FRONTMATTER = re.compile(rb"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
SAFE_TAGS = {
    f"tag:yaml.org,2002:{name}"
    for name in ("null", "bool", "int", "float", "binary", "timestamp", "omap", "pairs", "set", "str", "seq", "map")
}


@dataclass(slots=True)
class TaskDocument:
    metadata: Any
    body: bytes
    newline: str
    source_bytes: bytes | None = None


def load_task_document(path: Path) -> TaskDocument:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TaskError("task_read_failed", f"无法读取 {path}", {"path": str(path)}) from exc
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TaskError("task_invalid_utf8", "TASK.md 必须是 UTF-8 文件", {"path": str(path)}) from exc
    match = FRONTMATTER.match(raw)
    if not match:
        raise TaskError("frontmatter_invalid", "TASK.md 缺少合法 YAML frontmatter", {"path": str(path)})
    front = match.group(1).decode("utf-8")
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.allow_duplicate_keys = False
    try:
        tags = [token.value for token in yaml.scan(front) if isinstance(token, TagToken)]
        if any(_expanded_tag(handle, suffix) not in SAFE_TAGS for handle, suffix in tags):
            raise TaskError("frontmatter_unsafe_tag", "TASK.md 不允许自定义 YAML tag")
        metadata = yaml.load(front)
    except TaskError:
        raise
    except Exception as exc:
        raise TaskError("frontmatter_invalid", "TASK.md frontmatter 无法可靠解析", {"path": str(path)}) from exc
    if not isinstance(metadata, dict):
        raise TaskError("frontmatter_invalid", "TASK.md frontmatter 必须是 mapping", {"path": str(path)})
    return TaskDocument(
        metadata,
        raw[match.end() :],
        "\r\n" if b"\r\n" in match.group(0) else "\n",
        raw,
    )


def _expanded_tag(handle: str | None, suffix: str) -> str:
    if handle == "!!":
        return f"tag:yaml.org,2002:{suffix}"
    if handle is None:
        return suffix
    return f"{handle}{suffix}"


def dump_task_document(document: TaskDocument) -> bytes:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.width = 4096
    stream = io.StringIO()
    yaml.dump(document.metadata, stream)
    newline = document.newline
    front = stream.getvalue().replace("\n", newline).encode()
    return b"---" + newline.encode() + front + b"---" + newline.encode() + document.body


def dump_yaml(value: Any) -> str:
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    stream = io.StringIO()
    yaml.dump(value, stream)
    return stream.getvalue()
