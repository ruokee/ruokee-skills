# 操作状态与部分结果

本参考文档涵盖一个操作可能落地的三个技术状态——完成的 tmux 操作、部分操作和操作后观察——以及禁止盲重放规则。这些结果只描述 tmux 输入。本参考文档不定义高层协议状态机，其他参考文档链接至此获取阶段定义。

## 目录

- [三个技术状态](#三个技术状态)
- [为何存在部分阶段](#为何存在部分阶段)
- [send 输入阶段](#send-输入阶段)
- [生命周期 state-unknown 结果](#生命周期-state-unknown-结果)
- [操作后观察](#操作后观察)
- [中断](#中断)
- [禁止盲重放规则](#禁止盲重放规则)
- [恢复](#恢复)
- [参考导航](#参考导航)

## 三个技术状态

每个操作归约为三个技术状态之一：

1. **完成的 tmux 操作**——tmux 接受了粘贴、按键或生命周期命令，且控制器确认了结果画面。这仅表示 tmux 层面的成功；它从不声称目标 TUI 接受、解析或执行了输入。
2. **部分操作**——文本或按键可能已到达 pane，但控制器无法确认下一步（写入超时、提交键失败、操作后捕获失败）。精确阶段会指引检查。
3. **操作后观察**——操作后捕获的最新画面，供你判断。将 `changed` 和 `unchanged` 用作画面变化诊断；二者都不表示成功或失败。

## 为何存在部分阶段

tmux 接受只确认 tmux 收到了字节或按键。目标 TUI 是否接受、解析或执行仍然未知。写入文本、提交文本、捕获结果是三次独立的 tmux 操作，其中任何一个都可能独立失败或超时。控制器报告它所到达的精确阶段，从不将这些阶段折叠成单一的布尔值"已投递"。

## send 输入阶段

`send` 在一个 pane 锁下运行输入序列：重新检查目标身份，捕获基线，将正文加载到 buffer（`load-buffer`），粘贴（`paste-buffer -p`），并发送提交键（`Enter`）。随后控制器释放锁，再捕获有界的操作后画面。报告的阶段：

| 阶段 | 含义 | 可安全重放？ |
| --- | --- | --- |
| `text_not_written` | `load-buffer` 在确认任何 pane 粘贴前失败；文本假定未送达 | 是——没有任何内容到达 pane |
| `text_written_not_submitted` | 粘贴可能已到达 pane 但提交未确认。涵盖失败或超时的 `paste-buffer`，以及非超时的提交键失败 | 否 |
| `submitted_state_unknown` | 提交键可能已到达 pane：提交键命令超时，或发送键后操作后捕获失败 | 否 |
| `submitted` | tmux 接受了粘贴和提交键，且在锁释放后捕获了操作后画面；仍不声称 TUI 接受 | 不适用（已成功） |

所有正文走相同的粘贴路径，无论长度和换行数——没有单独的多行门控。

## 生命周期 state-unknown 结果

`launch`、`key` 和 `close` 各自存在一个 state-unknown 结果，当 tmux 已执行操作但控制器无法确认结果状态时（通常是变更后的捕获失败或超时）出现：

| 命令 | state-unknown 阶段 | 含义 |
| --- | --- | --- |
| `launch` | `launch_state_unknown` | pane 可能存在但无法确认启动状态。当 pane 创建本身超时时，连 pane 是否存在也不确定 |
| `key` | `key_state_unknown` | 按键事件可能已到达 pane；无法捕获结果 |
| `close` | `close_state_unknown` | `kill-pane` 命令失败或超时；pane 可能已经关闭 |

在每种情况下先解析并读取 pane，再执行下一次变更操作。

`launch` 还区分了干净退出的进程：`executable_not_found`（退出码 127）和 `launch_process_exited`（阶段 `process_exited`），在启动过程中已启动进程退出时检测到。Pane 以 `remain-on-exit` 保持存活，因此可以检查其最终画面。启动在就绪超时前未产生实质性画面变化时失败 `launch_timeout`。

## 操作后观察

`send` 和 `key` 在释放锁后返回 pane 的最新画面。快照可能已包含并发的后续 send，无法单独证明一次操作的效果。将其作为观察结果；`changed` 和 `unchanged` 只描述画面变化。

## 中断

在变更操作期间发生的 `KeyboardInterrupt` 会被报告为稳定的 `interrupted` 错误，映射到正确的部分阶段——文本写入后提交前中断报告 `text_written_not_submitted`；提交键之后中断报告 `submitted_state_unknown`；launch/key/close 期间中断报告相应的 `*_state_unknown`。

## 禁止盲重放规则

绝不在效果可能已经发生的任何阶段之后自动重新发送消息或重复变更操作——包括 `text_written_not_submitted`、`submitted_state_unknown`、任何 `*_state_unknown` 或 `interrupted` 结果。文本可能已位于 composer 中，或者按键/提交可能已经送达。先解析并读取 pane；如果目标文本确实存在，至多单独发送提交键（参见 [tmux-recovery.md](tmux-recovery.md)）。

## 恢复

从返回的 `screen` 尾部内容和 `recovery` 字段开始。当后端或 socket 不确定时运行 `doctor`。仅当控制器无法安全完成操作，或部分输入需要手工检查时，才回退到 [tmux-recovery.md](tmux-recovery.md)——原生 tmux 绕过 pane 锁和本阶段报告机制，因此应将其作为有意的最后手段。

## 参考导航

- [cli.md](cli.md) — 命令索引、JSON 信封以及阶段与错误码的区别。
- [messaging.md](messaging.md) — `send` 头部语法、params 以及产生这些阶段的输入队列。
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — TARGET 解析、pane 锁和 launch/wait/close。
- [presets.md](presets.md) — preset schema、pane 命名和私有 Agent 注册表。
- [adapters.md](adapters.md) — 各 CLI 的清输入和开始新对话差异。
- [tmux-recovery.md](tmux-recovery.md) — 控制器无法完成操作时的原生 tmux 恢复。
