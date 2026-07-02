---
name: python-engineering
description: Python engineering guidance for project layout, Python version policy, dependency management, coding specifications, type hints, testing, custom linting, Python grammar choices, standard-library usage, tooling, and Python code review. Use when asked to review, design, or discuss Python-specific conventions, project structure, package layout, dependency setup, typing/testing/linting specs, grammar usage, stdlib mechanisms, or Python project engineering practices.
---

# Python Engineering

在进行 Python 相关的工程评审、规范设计和分析时使用这个 Skill。它涵盖项目形态、Python 版本策略、包结构、类型标注、测试、自定义 lint、语法选择、标准库机制、工具链，以及面向 Python 的代码评审。

对于普通的 Python 代码评审或日常自检，除非用户明确缩小范围，否则也应同时使用 `code-quality`。

## 进入条件

当任务是 Python 专属工程决策时启用此 Skill：项目形态或包布局、Python 版本策略、依赖管理、type hints 与类型检查策略、测试、docstring、自定义 lint、语法选择、标准库机制或工具链设置。

## 模式选择

提供三种模式。默认使用 fast review。

|模式|触发条件|读取|
|-|-|-|
|Fast review|日常自检、较小 diff、PR review 的默认模式|`workflow/fast-review.md`|
|Full review|用户明确说“full review”、“complete review”、“systematic review”|`workflow/full-review.md`|
|Analysis|用户在讨论、头脑风暴、设计比较、机制分析或重构方案时|`workflow/analysis.md`|

只读约束：当用户说“不要修改”、“read-only”、“just analyze”或“survey”时，不要运行任何写文件的命令。优先使用 `rg`、`git ls-files`、`git show`、`find`、`wc`、`nl`。避免使用 `uv run`、`pytest`、`ruff check --fix`、`pre-commit run`，或任何会创建 `.venv`、缓存或修改源码的命令。

## 判断顺序

根据信号路由到叶子文档。只读取任务所需的内容。

|信号|先读|常配合|
|-|-|-|
|Python 版本、运行时目标、兼容性|[python-version](references/project/python-version.md)|type-hint, structure|
|项目形态：脚本、flat、src、packaged app、workspace|[structure](references/project/structure.md)|dependency-management, uv|
|运行时 / 开发 / 可选依赖、lock、groups|[dependency-management](references/project/dependency-management.md)|uv, structure|
|代码风格、PEP 8 与 formatter / review 边界|[style](references/spec/style.md)|ruff, custom-lint|
|type hints、annotations、`Any`、`cast`、Protocol、generics、type alias、type parameters|[type-hint](references/spec/type-hint.md)|python-version, ty|
|测试结构、fixture、parametrize、行为覆盖|[testing](references/spec/testing.md)|pytest, coverage|
|docstring、API docs、schema metadata、信息放置|[docstrings-api-docs](references/spec/docstrings-api-docs.md)|type-hint|
|项目专属机械规则、自定义 lint|[custom-lint](references/spec/custom-lint.md)|flake8-plugin, pre-commit|
|`match`/`case`、structural pattern matching|[match-case](references/grammar/match-case.md)|type-hint|
|`with`、`async with`、资源生命周期语法|[context-manager](references/grammar/context-manager.md)|contextlib, exception-groups|
|`ExceptionGroup`、`except*`、multi-error|[exception-groups](references/grammar/exception-groups.md)|context-manager|
|Decorators、higher-order functions、parameterized decorators、decorator classes|[decorator](references/grammar/decorator.md)|functools, common|
|常见 stdlib：pathlib、enum、dataclasses、logging|[common](references/stdlib/common.md)|functools, itertools|
|`singledispatch`、`partial`、closure、decorator helpers|[functools](references/stdlib/functools.md)|decorator, common|
|`itertools`、lazy pipelines、grouping、batching|[itertools](references/stdlib/itertools.md)|common, functools|
|`contextlib`、`ExitStack`、`AsyncExitStack`|[contextlib](references/stdlib/contextlib.md)|context-manager, common|
|uv 依赖、lock、script、workspace 命令|[uv](references/tooling/uv.md)|dependency-management, structure|
|Ruff formatter / linter 的职责|[ruff](references/tooling/ruff.md)|style, custom-lint|
|ty 作为快速 type checker、LSP 反馈|[ty](references/tooling/ty.md)|type-hint, mypy, basedpyright|
|mypy strict、legacy gate|[mypy](references/tooling/mypy.md)|type-hint, ty, basedpyright|
|basedpyright strict、Pyright 对比|[basedpyright](references/tooling/basedpyright.md)|type-hint, ty, mypy|
|pytest 配置、发现、import mode、fixtures|[pytest](references/tooling/pytest.md)|testing, coverage|
|coverage.py、branch coverage、阈值|[coverage](references/tooling/coverage.md)|testing, pytest|
|pre-commit hooks、local gate、CI 集成|[pre-commit](references/tooling/pre-commit.md)|custom-lint, ruff|
|Flake8 plugin 机制用于自定义 lint|[flake8-plugin](references/tooling/flake8-plugin.md)|custom-lint, pre-commit|

目录中的 `index.md` 文件仅用于人工导航和维护。只有在目录边界本身不清晰时才读取 `index.md`。

## 偏好

在确定相关叶子文档后，读取项目事实和可选偏好：

1. 读取最邻近适用的 `AGENTS.md` 或项目规则。
2. 读取 `pyproject.toml` 及相关配置：`.pre-commit-config.yaml`、Makefile、CI、测试配置。
3. 通过启发式方式查找偏好：
    - 先尝试项目级：`.agents/preferences/python-engineering.md`，然后 `.agents/preferences/python-engineering/index.md`。
    - 如果没有，再尝试用户级目录：`~/.codex/preferences/python-engineering.md`、`~/.claude/preferences/python-engineering.md`，或等价的用户配置目录。
4. 如果任何层级都没有找到偏好，则静默继续。

偏好可能包含：最低 Python 版本、禁止导入、默认工具、docstring 风格、测试约定、第三方库 Skill 参考。不要把偏好当作 Python 语言事实或普适工程结论来陈述。

## 输出契约

先报告 findings。把事实、推断、判断、偏好和建议分开，不要混在一起。不要重复 formatter、linter 或 type checker 可以机械判定的问题。

输出格式按模式而定——遵循对应的 workflow 文档（`workflow/fast-review.md`、`workflow/full-review.md` 或 `workflow/analysis.md`）。分析模式给选项和取舍，而不是 findings 列表。

输出语言遵循全局/项目/用户指令；未明确指定时，使用当前对话的语言。

## 停止规则

- 不要自动运行 full review 模式。
- 除非用户要求修复，否则不要修改代码。
- 未经明确确认，不要运行不安全修复、批量 suppress、跨文件重构或依赖变更、会改变 lockfile 的命令。
- 不要把偏好当作通用 Python 规则。
- 在只读或分析任务中不要写文件修改。
- 不要报告 Ruff、ty、mypy 或 pre-commit 可以机械发现的问题 - 如有必要只在 Notes 中提一次，然后继续。
