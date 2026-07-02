# Ruff

Ruff 是一个快速的 Rust-based formatter 和 linter，把 Black、Flake8、isort、pyupgrade 以及许多 Flake8 plugin 的工作整合到一个工具里。它承担两项职责：`ruff format` 负责机械性的布局，`ruff check` 负责 lint 规则。将二者放在同一工具链中，意味着共享配置和一致、快速的反馈。

## Formatter

`ruff format` 负责重排布局：换行、缩进、引号、括号、空行和尾随逗号。它以 Black 兼容为目标，因此输出风格与 Black 很接近，在 Black 代码库上采用它通常只会带来很小的变更量。机械性的东西应完全交给它，并停止人工 review 格式。它是确定性的，适合在每次保存时以及 pre-commit 中运行。

```bash
ruff format
ruff format --check    # CI: fail if not formatted
```

默认风格保持 Black 兼容。preview style 会启用正在进行中的格式化变化；除非项目接受随着 style 演进而定期产生重新格式化 diff，否则应保持关闭。配置写在 `[tool.ruff.format]` 下，例如 `docstring-code-format` 可用于格式化 docstring 中的代码块，这一功能是可选的，默认未开启。

## Linter

`ruff check` 会运行按前缀分组的 lint rule family：`E` / `W`（pycodestyle）、`F`（Pyflakes）、`I`（isort 导入排序）、`UP`（pyupgrade 现代化）、`B`（bugbear）、`SIM`（simplify）、`C4`（comprehensions）、`RET`（return）、`RUF`（Ruff 原生），以及更多。像 `E`、`F`、`I`、`UP`、`B` 这样的小型起始集合，就能捕获真实缺陷，同时不会把项目淹没在风格噪音里。

```bash
ruff check
ruff check --fix
```

导入排序来自 `I` family，因此不需要单独的 isort。不要使用 `select = ["ALL"]`：那会把 lint 变成 micro-preference 的集合，而每增加一个 family 都会带来误报成本、review 认知成本、自动修复安全风险以及旧代码的迁移成本。应随着需要逐步加入 `SIM`、`RUF`、`C4`、`PIE`、`RET` 等 family。

## 规则成熟度

规则分为 stable 和 preview。stable 规则通过 `select` 启用；preview 规则则需要 preview mode，而且可能发生变化。应把 preview 规则视作可选实验，而不是默认项，这样规则集就不会在 Ruff 升级时自行漂移。

## `ruff check --fix` 的行为

`--fix` 会应用 Ruff 认为安全的修复，例如删除未使用的 import 和整理 import 顺序。unsafe fixes 可能改变行为或意图，需要通过 `--unsafe-fixes` 才会启用。应审查自动修复 diff，而不是盲目提交，尤其是在对遗留代码库进行批量修复时，因为在特殊代码上，所谓“安全”的修复也可能带来惊喜。

## 配置

配置写在 `pyproject.toml` 的 `[tool.ruff]` 下，规则选择在 `[tool.ruff.lint]`，格式化配置在 `[tool.ruff.format]`。`target-version` 和 `line-length` 只需设一次，formatter 和 linter 两边共享即可。per-file ignore 可处理合理的例外，例如放宽 `__init__.py` 中的 import 规则。

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

## Ruff 负责什么，哪些需要人工 review

Ruff 负责格式化和大范围机械 lint，这正是那些不该进入人工 review 的噪音。它不会判断命名质量、模块职责、异常上下文、类型边界设计、docstring 的信息价值或架构；这些需要 type checker、测试和人工 review。Ruff 的安全规则（`S`，来自 Bandit）只是低成本的静态提醒，不是完整的 SAST 或 dependency-vulnerability 扫描，也不能替代专门工具或人工安全 review。
