# Standard Library References

当标准库机制是任务核心时，阅读这些文件。每个文件都会解释该机制、它解决的问题、惯用用法，以及它停止起作用的边界。

- [`common.md`](common.md)：高频模块 - `pathlib`、`enum` / `StrEnum`、`dataclasses`、`logging`、`collections`，以及运行时 `typing` 工具。在选择合适的值容器、路径 API、有限值集合或日志形态时阅读。
- [`functools.md`](functools.md)：`singledispatch`、`partial`、`lru_cache` / `cache`、`reduce` 和 `wraps`。在做基于类型的分派、部分应用、memoization 和 decorator 支持时阅读。
- [`itertools.md`](itertools.md)：lazy iteration、batching、grouping、chaining，以及多次消费陷阱。在构建数据 pipeline 或变换序列时阅读。
- [`contextlib.md`](contextlib.md)：`@contextmanager`、`ExitStack`、`suppress`、`redirect_*`、`nullcontext` 和 `closing`。在编写或组合 context manager 时阅读。

标准库是默认 dependency。只有当 stdlib 机制确实不够用时，才去使用第三方 package，而不是反过来。这些参考文档描述的是机制，不是评审规则；评审工作流位于 [`../../workflow/`](../../workflow/index.md)。
