# 操作状态与部分结果

本参考文档涵盖每个原子操作的阶段、`*_state_unknown` 结果、禁止盲重放规则以及各命令共享的恢复边界。其他参考文档链接至此，而非重复说明阶段。

## 目录

- [为何存在阶段](#为何存在阶段)
- [send 与 request 输入阶段](#send-与-request-输入阶段)
- [生命周期 state-unknown 结果](#生命周期-state-unknown-结果)
- [中断](#中断)
- [禁止盲重放规则](#禁止盲重放规则)
- [恢复](#恢复)

## 为何存在阶段

tmux 接受字节或按键，并不等于目标 TUI 接受、解析或执行了它们。写入文本、提交文本、捕获结果是三次独立的 tmux 操作，其中任何一个都可能独立失败或超时。因此控制器报告它所到达的精确阶段，从不将这些阶段折叠成单一的布尔值"已投递"。每个输入结果还携带 `tui_acceptance: "unverified"`。

## send 与 request 输入阶段

`send`（以及 `request` 的分发部分）在一个 pane 锁下运行：重新验证已观察的身份，写入字面文本或受 adapter 门控的 bracketed paste，消费观察凭据，等待 adapter 的稳定延迟，发送提交键，并捕获有界的提交后画面。报告的阶段：

| 阶段 | 含义 | 可安全重放？ |
| --- | --- | --- |
| `text_not_written` | 字面输入或粘贴步骤失败；文本假定未送达 | 是——什么都没写入 |
| `text_written_not_submitted` | 文本可能已到达 pane；提交未确认。涵盖提交键命令失败**和**写入超时（超时写入保守地报告为此阶段，而非 `text_not_written`） | 否 |
| `submitted_state_unknown` | 提交的投递情况未知——tmux 接受了提交键但提交后捕获失败，或提交键命令本身超时 | 否 |
| `submitted` | tmux 接受了文本和提交键，且成功捕获提交后画面；`tui_acceptance` 仍为 `unverified` | 不适用（已成功） |

多行文本在未经验证 bracketed-paste 支持的 adapter 上会提前在 `text_not_written` 阶段失败，报 `multiline_not_safe`，在写入任何内容之前。

对于 `request`，分发失败映射为 ticket 阶段：`text_written_not_submitted` 或 `submitted_state_unknown` 变为 `dispatch_unknown`（child 可能已持有 request ID，任务可能已到达，因此仍接受 reply）；其他失败变为 `aborted`（拒绝 reply）。Reply TTL 的起始时间依次使用 `dispatched_epoch`、`dispatch_finished_epoch`、`created_epoch`。

## 生命周期 state-unknown 结果

`create`、`launch`、`restart`、`key` 和 `close` 各自存在一个 state-unknown 结果，当 tmux 已执行操作但控制器无法确认结果状态（通常是由于捕获失败或操作后超时）时出现：

| 命令 | state-unknown 阶段 | 含义 |
| --- | --- | --- |
| `create` | `create_state_unknown` | pane 存在但无法确认其初始画面/观察 |
| `launch` | `launch_state_unknown` | pane 和进程存在但无法确认启动状态 |
| `restart` | `restart_state_unknown` | pane 身份或进程可能已变化；新的 run 可能或可能未运行 |
| `key` | `key_state_unknown` | 按键事件可能已到达 pane；无法捕获结果 |
| `close` | `close_state_unknown` | pane 可能已经关闭 |

在每种情况下 pane 存在（对于 `close` 可能已消失）；在再次执行变更操作之前，先解析并读取 pane。

`launch`/`restart` 还区分了干净退出的进程：`executable_not_found`（退出码 127）和 `launch_process_exited`（阶段 `process_exited`）。Owned pane 以 `remain-on-exit` 保持存活，因此可以检查其最终画面并使用 `restart` 在原地修正。

## 中断

在变更操作期间发生的 `KeyboardInterrupt` 会被报告为稳定的 `interrupted` 错误，映射到正确的部分阶段——例如，文本写入后提交前中断报告 `text_written_not_submitted`；提交键之后中断报告 `submitted_state_unknown`；create/launch/restart/key/close 期间中断报告相应的 `*_state_unknown`。在文本可能已到达的位置，观察凭据已被消费。在 v2 `reply` 中，一旦事件文件已发布，中断无法回滚：事件保留，只有 notification 诊断记录中断。

## 禁止盲重放规则

绝不在效果可能已经发生的任何阶段之后自动重新发送消息或重复变更操作——包括 `text_written_not_submitted`、`submitted_state_unknown`、任何 `*_state_unknown` 或 `interrupted` 结果。文本可能已位于 composer 中，或者按键/提交可能已经送达。先解析并读取 pane；如果目标文本确实存在，至多单独发送提交键（参见 [tmux-recovery.md](tmux-recovery.md)）。

## 恢复

从返回的 `screen` 尾部内容和 `recovery` 字段开始。当后端或 socket 不确定时运行 `doctor`。仅当控制器无法安全完成事件，或部分输入需要手工检查时，才回退到 [tmux-recovery.md](tmux-recovery.md)——原生 tmux 绕过观察凭据、所有权、per-pane 锁和本阶段报告机制，因此应将其作为有意的最后手段。
