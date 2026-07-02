# Common Standard Library Modules

本文汇总了高频标准库模块的简短参考。每个模块都解决一个狭窄且反复出现的问题；选对它可以移除容易写错的小型手工代码。下面这些模块彼此无关，因此各自独立 - 不存在覆盖它们的统一决策表。

## pathlib

`pathlib` 用对象而不是字符串来建模 filesystem path。`Path` 带有平台感知语义：用 `/` 连接、拆分成 `parts`、读取 `.name` / `.stem` / `.suffix`，以及按照当前 OS 分隔符进行解析。

```python
from pathlib import Path

config = Path("config") / "settings.toml"
text = config.read_text(encoding="utf-8")
for log in Path("logs").glob("*.log"):
    archive(log)
```

优先使用 `Path` 而不是 `os.path` 字符串操作：`config / "settings.toml"` 比嵌套在 f-string 里的 `os.path.join` 更不容易出错，而且对象本身就说明了意图。`read_text`、`write_text`、`mkdir(parents=True, exist_ok=True)` 和 `iterdir` 等方法足以覆盖大多数文件操作，而无需 `open` 样板代码。

在 API 边界应接受 `os.PathLike[str]`（或 `str | Path`），这样调用者可以传字符串或 `Path`；在入口处只转换一次为 `Path` 即可。不要在路径字面量里假设 POSIX 分隔符 - 让 `pathlib` 处理 `/` 与 `\` 的差异。只有当路径跨越文本边界（例如序列化或 subprocess 参数）时，才保留原始字符串。

## enum / StrEnum

`enum` 定义了一组有限且具名的值。当字段具有封闭域 - states、modes、categories - 时，应使用它，而不是裸字符串或魔法整数，这样类型检查器就能约束它。

```python
from enum import Enum, StrEnum, auto

class Color(Enum):
    RED = auto()
    GREEN = auto()

class Role(StrEnum):
    ADMIN = "admin"
    VIEWER = "viewer"
```

`StrEnum`（3.11+）的成员 _本身就是_ 字符串，因此它们可以直接与普通字符串序列化和比较 - 这对 JSON、config 和数据库列很方便。普通 `Enum` 会让成员与其值保持区分，当你想禁止意外字符串比较时更安全。`IntFlag` / `Flag` 用于建模可用 `|` 组合的位集选项。

Enum 让完备性更显眼：对 enum 成员做 `match` 时，可以检查是否缺少 case。对于开放式或经常变化的值集合，则不应使用 enum，因为它会带来仪式感却没有回报。序列化时，应把 wire format 固定为 `.value`（或使用 `StrEnum`），而不是 `.name`，这样重命名成员不会悄悄破坏已存数据。

## dataclasses

`dataclasses` 会为主要承载结构化数据的 class 生成 `__init__`、`__repr__` 和 `__eq__`。它适合 value object、配置包和 DTO，即字段本身就是类型的情况。

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, kw_only=True, slots=True)
class Endpoint:
    host: str
    port: int = 443
    headers: dict[str, str] = field(default_factory=dict)
```

mutable default 应使用 `default_factory` - 裸的 `[]` 或 `{}` 会在实例之间共享，这是经典 bug。`frozen=True` 让实例可哈希且不可变；`kw_only=True` 能在字段增多时避免位置参数脆弱性；`slots=True` 则能减少内存并阻止意外属性拼写。

当你面对的是行为很少的普通数据时，选 dataclass。需要更丰富的 validation hook 或 converter、但又不想引入完整 framework 时，可以考虑 `attrs`；当你需要对外部/不可信输入（request body、配置文件）进行运行时解析和验证时，则应使用 `pydantic`。dataclass 在运行时不做任何验证 - 它的 annotations 只是提示，不是守卫。关于如何对 dataclass field 做 pattern matching，见 [`../grammar/match-case.md`](../grammar/match-case.md)。

## logging

`logging` 将 _发出_ diagnostic event 与 _决定_ 它们去向分离开。核心区分是：**library** 只配置命名 logger 并发出记录，但绝不配置 handler 或 level；**application** 在启动时统一负责 handler、level 和 format 配置。

```python
import logging

logger = logging.getLogger(__name__)

def fetch(url: str) -> bytes:
    logger.debug("fetching %s", url)
    try:
        return _download(url)
    except DownloadError:
        logger.exception("download failed for %s", url)
        raise
```

在 `except` 块中使用 `logger.exception(...)` 可以自动捕获 traceback；不要用 `logger.error(str(exc))`，那会丢失 stack。把 message 参数作为 `%s` 参数传入，而不是预先格式化成 f-string，这样在 level 被禁用时格式化会被跳过。对于结构化日志，可以通过 `extra=` dict 或结构化日志 library 附加上下文，而不是把字段拼接进 message 文本。library 应该给顶层 logger 添加一个 `NullHandler`，在 application 配置输出之前保持静默。

## collections

`collections` 提供了一些专门的容器，用来替代容易出错的手工模式。

```python
from collections import Counter, defaultdict, deque

counts = Counter(words)                 # frequency tallies
groups: dict[str, list[int]] = defaultdict(list)
recent: deque[int] = deque(maxlen=100)  # bounded ring buffer
```

`defaultdict` 去掉了“先检查再初始化”的分组舞步；`Counter` 提供 `most_common` 和计数算术；`deque` 提供两端 O(1) 的 append/pop，以及 list 无法高效实现的 `maxlen` 环形缓冲。`namedtuple` 早于 dataclass 出现，如今仍适合轻量、不可变的记录，尤其是兼容 tuple 的返回值 - 但只要涉及行为、默认值或不断演进的字段，就应优先使用 `@dataclass`，因为它更易读，也更易扩展。

## typing 运行时工具

`typing` 的大部分内容在 runtime 会被擦除，但也有少量工具就是为运行而设计的。`typing.get_type_hints(obj)` 会把 annotations 解析成真实对象，连同字符串/forward references 一起求值 - 这是读取 annotations 的 framework 的正确入口，而不是直接碰 `__annotations__`。`TypeGuard`（以及 3.13 的 `TypeIs`）可以标注函数返回值，使 type checker 在返回 `True` 时收窄参数类型：

```python
from typing import TypeGuard

def all_str(items: list[object]) -> TypeGuard[list[str]]:
    return all(isinstance(x, str) for x in items)
```

`@runtime_checkable` 允许把 `Protocol` 用于 `isinstance`，但它只检查属性 _是否存在_，不检查 signature，因此应把它当作粗粒度守卫。对于 Python 3.14+ 的 runtime introspection，优先使用 `annotationlib.get_annotations()`，因为它是围绕 deferred-annotation 语义设计的。把运行时类型逻辑保持在边界上；不要把 `isinstance` 链散落在本可以由 type checker 静态验证的代码里。
