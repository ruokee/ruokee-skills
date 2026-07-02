# basedpyright

basedpyright 是 Pyright 的社区分支。它与 Pyright 在性能、import resolution 和 LSP 行为上保持紧密跟进，但默认更严格、diagnostic 更多、支持 baseline，并可通过 PyPI 安装。它最适合作为严格 type-check 的交叉参考，以及在 editor 与 CLI 结果保持一致时使用。

## 与 Pyright 的关系

Pyright 提供了基础：一个快速的 type checker，具备强大的 language server 支持、CLI 执行、import resolution 以及核心 typing 规则。basedpyright 是在此基础上继续跟进 upstream、并增加维护者认为缺失内容的 fork。Pyright 的能力可以作为 basedpyright 的 upstream 证据，但两者并不完全相同，因此 Pyright 文档只能说明基线，而不能说明 basedpyright 的具体行为。

## 默认严格度差异

最显著的区别是：basedpyright 默认就比 Pyright 更严格。它会把许多 Pyright 只是 warning 或默认关闭的 diagnostic 提升为 error，因此一个在 Pyright 下干净的代码库，在 basedpyright 下可能一下冒出一大批新问题。这正是这个 fork 的目的：默认就表达更高要求。

## `reportUnusedX` 与额外诊断

basedpyright 增加并启用了超出 Pyright 集合的诊断，包括更严格的 `reportUnused*` 规则（未使用的 import、变量、表达式等）以及对逃逸到其他地方的 `Any` 使用的报告。这些规则能捕获死代码和静默的 `Any` 泄漏，但在大型既有代码库上，它们需要 baseline 才不会在初次运行时得到无法承受的报告量。

## 基线采用

对于已有项目，basedpyright 支持 baseline file，用来记录当前发现的问题，这样只有新问题才会让 gate 失败。这是在半路采用它的实际路径：先捕获 baseline，守住新代码，再逐步清理已记录的问题，而不是在第一次跑出绿色之前就把所有问题修完。

## IDE 集成

basedpyright 提供 language server，并与编辑器集成，包括在开源 VS Code 构建之外获得类似 Pylance 的能力。因为编辑器和 CLI 用的是同一引擎，所以内联反馈和 gate 能保持一致，这也是它在严格工作流中很有吸引力的一大原因。

## 何时有价值

如果 [ty](ty.md) 作为默认 gate，basedpyright 更适合作为历史严格 profile、迁移交叉检查、棘手 inference 情况的验证器，或外部协作期间的补充。它不会取代 ty 成为默认。除非项目规模、风险和收益确实值得配置成本，否则不要永久同时开着 ty、[mypy](mypy.md) 和 basedpyright 这三道 gate。启用 basedpyright 时，应显式定义 baseline、suppression 风格、strict rules、目标 Python 版本和 import resolution，这样结果才能在不同机器和 CI 上保持可复现。
