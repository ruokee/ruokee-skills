# Specification References

当任务的核心是 coding conventions、typing、testing、documentation 或项目专属规则时，阅读这些文件。每个文件都是参考资料：它解释某条约定是做什么的、边界在哪里，而不是一个要机械执行的 checklist。

- [`style.md`](style.md)：formatter 和 linter 机械处理的部分，与仍需人工判断的部分之间的边界 - 命名、模块边界、抽象层次，以及在 PEP 8 基线之上的显式性。
- [`type-hint.md`](type-hint.md)：把 type annotations 视为接口契约 - type parameters 和 aliases、渐进式 typing 策略、`Any` 的收敛、Protocol 与 ABC、`TYPE_CHECKING` 隔离，以及各 type checker 的关系。
- [`testing.md`](testing.md)：测试组织、fixture 设计、parametrization、以行为覆盖而非行覆盖为目标、mock 边界，以及把测试当作可执行文档。
- [`docstrings-api-docs.md`](docstrings-api-docs.md)：不同信息该放在哪里 - signature、docstring、schema metadata 还是 documentation site - 以及什么时候 docstring 能增值、什么时候只是重复 signature。
- [`custom-lint.md`](custom-lint.md)：何时值得建立项目专属 lint rule，如何设计一个机械且低误报的规则，以及它应当在哪里运行。

这些文档描述的是约定及其取舍，而不是评审政策。评审工作流位于 [`../../workflow/`](../../workflow/index.md)。
