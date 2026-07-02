# ty

ty 是 Astral 团队推出的快速 Rust-based type checker 和 language server，该团队也是 Ruff 和 uv 的作者。它的设计目标是速度和紧密的 editor 集成：既要快到可以通过 LSP 在每次击键时运行 type checker，又要有适合 CI 门禁的 CLI。

## 速度优势

它最显著的特征是增量速度。Rust 核心让 ty 在大型项目上的重新检查时间，比 mypy 或 pyright 快得多，这既保持了编辑器反馈回路的紧密，也让 CI 类型门禁成本更低。快速反馈正是它早期采用的根本原因：运行成本足够低，因此不会拖慢日常工作。

## 它检查什么

ty 承担静态 type checker 该做的工作：项目内的完整类型覆盖、接口边界、`Any` 泄漏、类型收窄、可达性分析，以及不可达代码检测。它同时服务于编辑器（通过 LSP）和命令行，因此开发者在内联里看到的检查，CI 中也会运行同样的内容。

```bash
ty check
```

## 成熟度与限制

ty 比 mypy 和 pyright 更新，因此仍处于早期采用路径上。它尚不能被证明覆盖 older checkers 所处理的每一种 typing 场景，而且对每个第三方 stub、边缘 inference，以及最新 Python 语义的覆盖，都需要项目级验证，而不能直接假定。应把它视为高潜力且能力很强的工具，但在具体项目上要验证其行为，而不是盲目信任。

## 与 mypy 和 pyright 的关系

ty 与 [mypy](mypy.md) 和 [basedpyright](basedpyright.md) 竞争 primary checker 位置。取舍是明确的：ty 提供速度和编辑器响应性；mypy 和 pyright / basedpyright 提供更成熟的生态，而 basedpyright 还提供更严格的默认值。把 ty 选为默认门禁，意味着你认为快速反馈比成熟度差距更重要；而在发布 library、外部协作或迁移时，旧的 checker 仍然可以作为比较层保留。

## 配置与采用

在 `pyproject.toml` 的 `[tool.ty]` 表中配置 ty，并且要明确设置规则严格度，而不是一次性启用所有实验性诊断。早期采用的风险控制方式是：锁定工具版本、保留项目级配置、在 CI 中验证，并在遇到特定类型问题时仍能调用 mypy 或 basedpyright 作为交叉检查。把版本锁住，避免工具升级悄悄改变会触发哪些诊断。

## 它能抓住什么、会漏掉什么

ty 能捕获大类静态类型错误：参数类型不匹配、返回值错误、`None` 处理、收窄失败，以及不可达分支。它可能漏掉的是：第三方 stub 尚不成熟、最新语言语义，或者 older checker 多年打磨过的推断边角情况。当 ty 与成熟 checker 在某个难题上意见不一致时，应先调查，而不是预设 ty 一定错或一定对。
