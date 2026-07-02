# Flake8 Plugin

Flake8 plugin 是一个 Python package，它注册 AST 或 token visitor 来产生自定义 lint warning。它允许项目强制执行通用 linter 无法覆盖的领域或架构规则：禁止某些 import、要求特定 decorator 模式、模块边界违规、与 framework 语义相关的命名约定，或对特定基类的结构性约束。

## 工作方式

Flake8 plugin 在 AST 层运行。它们接收解析后的 tree（或原始 token / line），并产出 `(line, col, message, type)` 元组。plugin 通过 `pyproject.toml` 中的 `entry_points`，以 `flake8.extension` group 的形式注册。

一个最小的 AST 检查器 plugin 需要：

1. 一个带有 `name` 和 `version` class attribute 的 class。
2. 一个 `__init__(self, tree)`，接收 AST（对于 AST checker）或 `__init__(self, tree, filename)`。
3. 一个 `run(self)` generator，产出 `(line, col, message, type)`。
4. 通过 `pyproject.toml` 中的 `[project.entry-points."flake8.extension"]` 进行注册。

对于基于 token 或 physical-line 的 checker，还有其他注册钩子，但 AST checker 最常见，因为它们能够访问完整 parse tree，适合结构性规则。

## 何时适合使用 plugin

- 规则是机械的：可以仅从 AST 评估，无需 runtime 信息。
- 规则在正确限定范围后误报率很低。
- 规则对整个 codebase 都一致适用，而不是只针对一两个 module。
- 规则原本会消耗大量重复的人工 review 精力。
- 规则无法通过 [Ruff](ruff.md) 的规则配置或 `select` / `ignore` 组合表达。

## 何时不适合使用 plugin

- 检查需要 runtime type resolution、跨 module data flow，或超出 AST 所能提供的 import resolution。这些属于 type checker，而不是 lint plugin。
- 规则是主观的或依赖上下文判断，更适合 review judgment。
- [Ruff](ruff.md) 或其他现有工具已经覆盖了该检查。在编写自定义 plugin 之前，先确认 Ruff 是否原生支持该规则族（例如 `flake8-bugbear`、`flake8-comprehensions`）。
- 规则只适用于一两个文件；写注释或 review note 就够了。
- 维护 plugin 的成本高于它防止的 bug 数量。

## 测试

通过对 synthetic AST snippet 调用来测试 plugin：

- 用 `ast.parse` 解析代码字符串。
- 用 tree 实例化 checker class。
- 从 `run()` 收集结果。
- 对正例断言预期的 line / col / message 元组，对反例断言结果为空。

做集成测试时，可以对 fixture 文件运行 `flake8 --select=YOUR_CODE`，让文件同时覆盖触发和不触发的模式。

## 与 Ruff 的关系

Ruff 已经原生实现了许多 Flake8 plugin rule set。在编写自定义 plugin 之前，先确认 Ruff 是否已经覆盖了该规则族。如果覆盖了，应优先使用 [Ruff 配置](ruff.md)。

自定义项目专属 plugin 仍然很有价值，因为 Ruff 不支持任意用户定义的 AST visitor。真正需要自定义结构性检查的项目，仍然需要 Flake8 plugin（或者其他方案：通过不稳定 plugin API 编写自定义 Ruff 规则，或在 [pre-commit](pre-commit.md) 中运行独立 AST 脚本）。

与 [custom lint specification](../spec/custom-lint.md) 的关系是：spec 文档定义 _应该创建什么_ 项目专属规则，以及 _如何思考_ 规则设计；本文档则覆盖实现和运行这些规则时使用的 Flake8 plugin _机制_。

## 错误信息设计

一个可操作的错误信息应当告诉开发者：

- 检测到了什么（违规本身）。
- 为什么重要（简短说明）。
- 应该怎么做。

消息前缀使用简短代码（例如 `PRJ001`），便于选择性 suppress。保持消息不超过一行。如果某条规则需要大量说明，可以在 message 中链接到内部文档。
