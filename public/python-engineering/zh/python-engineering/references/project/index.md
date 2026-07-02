# Project Shape References

当任务的核心是决定项目的总体形态、支持的运行时，或依赖边界时，阅读这些文件。每个文件都是参考：它解释的是选择背后的力量，而不是一个要机械套用的 checklist。

- [`python-version.md`](python-version.md)：如何选择最低和目标 Python 版本，`requires-python` 的含义，近几年各版本解锁了哪些特性，以及何时有理由提高最低版本。
- [`structure.md`](structure.md)：每种常见项目形态 - 单文件脚本、flat layout、src layout、packaged application 和 workspace - 的完整说明，以及区分它们的信号和选择决策表。
- [`dependency-management.md`](dependency-management.md)：runtime/dev/optional/internal 的划分、lockfile 策略、dependency groups、版本约束，以及 monorepo 中的依赖方向。

这些文档描述的是作用力和取舍，而不是评审规则。它们提供判断具体项目所需的上下文；评审工作流本身位于 [`../../workflow/`](../../workflow/index.md)。
