# Full Review — Python Engineering

系统化、基于证据的 Python 工程评审。比 fast review 更重：分阶段读取、验证高严重度 findings，并在给出有风险建议前先征求确认。只有用户明确要求时才进入这个模式。

## 触发条件

用户明确说“full review”、“complete review”、“systematic review”或“architecture review”。不要自行进入这个模式。

## 前提

- 默认只读。只有在用户要求修复时才修改代码。
- 先确认范围再广泛阅读：是哪一个 package、module 或 subsystem，这次 review 的目的是什么（发布、交接、重构决策）。
- 先读，再判断，别靠猜。

## 步骤

1. 上下文接收。在阅读代码前，把工作分成四类：
    - 必须阅读 —— 没有它们 review 就不可能正确。
    - 应该阅读 —— 相邻代码、测试和配置，会影响判断。
    - 已知 —— 对话中已经建立的事实；不要重复推导。
    - 不确定 —— 需要通过阅读或询问用户来解决的问题。
2. 分阶段阅读，而不是一口气全读。
    - 项目事实：`pyproject.toml`（`requires-python`、依赖、groups、工具配置）、`.pre-commit-config.yaml`、CI、测试配置、Makefile。
    - 偏好：`.agents/preferences/python-engineering.md`，否则 `.../python-engineering/index.md`。如果没有就继续。
    - 根据下方 review matrix 逐步加载相关代码和测试。
3. 依据 review matrix 工作。对每一项，先收集证据再下判断：
    - 版本与依赖 - 语法 / stdlib 与 `requires-python` 是否一致；依赖是否声明正确，是否放在正确分组。
    - 布局、入口点、workspace - project shape、package 边界、script/console entry point、workspace 成员一致性。
    - 类型覆盖 - public signature 是否标注，`Any` / `cast` 是否有充分理由，Protocol / generics 是否在有价值时使用。
    - Docstring 与 API docs - public surface 是否有文档，信息是否放在读者会去找的地方。
    - 测试 - 关注行为覆盖而非行覆盖，fixture 和 parametrize 结构，断言是否有意义。
    - 自定义 lint - 项目专属的机械规则是否遵守；如有必要，记录可新增的规则候选。
    - 语法选择 - `match`/`case`、context managers、exception groups、decorators 是否用在合适位置，而不是装饰性使用。
    - stdlib 使用 - 是否使用 `functools`、`itertools`、`contextlib`、`pathlib`、`enum`、`dataclasses`、`logging` 代替手工实现。
    - 工具配置 - uv、Ruff、ty/mypy/basedpyright、pytest、coverage、pre-commit 是否配置一致且互不矛盾。
4. 对每一条高严重度 finding 自我复核。重新阅读证据，考虑一个合理的反例读法，并说明置信度。任何无法支持的内容都应降级或移除。
5. 确认停顿。在建议以下内容之前先停下来询问：
    - 不安全的修复或会写文件、创建 `.venv` / 缓存、或改变 lockfile 的命令。
    - 批量 suppress 或大范围配置调整。
    - 跨文件重构或依赖变更。
    - 行为变更型建议。

## 输出格式

按 matrix 分类分组输出 findings。每条 finding 用一个 block：

```text
- [severity, confidence] path:line Title
  Fact: observable code/config evidence.
  Impact: correctness, maintainability, readability, testability, runtime, or delivery cost.
  Judgment: Python engineering category.
  Preference: preference source path, if used.
  Evidence: support, counter-evidence, and remaining uncertainty.
  Recommendation: smallest sufficient change.
  Verification: command to run, or why none is needed.
```

最后附上：

```text
Open Questions
- Items needing user or project confirmation.

Notes
- Downgraded, tool-handled, or intentionally unreported items.
```

## 停止规则

- 未经明确要求，不要修改代码。
- 对不安全、批量、跨文件、依赖或行为变更建议要先确认。
- 不要把偏好当作 Python 语言事实或普适工程结论。
- 不要报告 Ruff、ty、mypy 或 pre-commit 机械能查出的内容 - 如有影响可在 Notes 中提一次，然后继续。
- 保持事实、推断、判断、偏好和建议彼此分离。
