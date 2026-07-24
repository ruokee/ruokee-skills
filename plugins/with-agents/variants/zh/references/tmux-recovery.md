# with-agents 的 tmux 故障恢复

仅当随附控制器无法完成操作、`doctor` 报告后端问题或需要手工恢复部分输入时，才阅读本文。原生 tmux 会绕过 per-pane 锁和结构化的部分阶段报告，只在需要 fallback 时使用。

## 目录

- [诊断 server 与 socket](#诊断-server-与-socket)
- [解析并检查 pane](#解析并检查-pane)
- [恢复部分 send](#恢复部分-send)
- [手工创建最小后端](#手工创建最小后端)
- [手工粘贴正文](#手工粘贴正文)
- [安全关闭 pane](#安全关闭-pane)
- [参考导航](#参考导航)

## 诊断 server 与 socket

从控制器的只读诊断开始：

```bash
<skill-root>/scripts/with-agents doctor
```

然后在不修改任何内容的情况下检查 tmux：

```bash
command -v tmux
tmux -V
printf '%s\n' "TMUX=${TMUX:-<unset>}" "TMUX_PANE=${TMUX_PANE:-<unset>}"
```

`$TMUX` 的格式为 `socket_path,server_pid,session_index`。socket 路径本身可能包含逗号，因此从右侧切掉尾部两个数字字段。从第一个逗号处切割会把含逗号的 socket 静默截断为错误路径。当 `$TMUX` 命名了预期的 live server 时，使用该精确 socket。不要从另一个 client 推断：

```bash
rest="${TMUX%,*}"          # drop session_index
socket_path="${rest%,*}"   # drop server_pid, keep the full socket path
tmux -S "$socket_path" list-sessions
tmux -S "$socket_path" display-message -p '#{socket_path}|#{pid}'
```

针对此现有 server 的每个原生 tmux 命令都携带同样的 `-S "$socket_path"`。省略它会将命令发送到 tmux 的默认 server，而默认 server 可能在同一个 `%id` 下持有不同的 pane——对捕获、粘贴、Enter 或 `kill-pane` 而言都是静默错误的目标。如果 `$TMUX` 已过期，不要将输入操作悄悄重定向到默认 server。与用户一起或从一个已知的精确 socket 找到预期的 server，然后以 `--socket PATH` 重新运行控制器命令。

## 解析并检查 pane

列出权威身份及其发现提示。Pane 通过 socket + pane ID 定位；公开名称为实时 `window_name`，pane PID 和死亡状态仅为诊断字段：

```bash
tmux -S "$socket_path" list-panes -a \
  -F '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|#{pane_pid}|#{pane_current_command}|#{pane_current_path}|dead=#{pane_dead}|name=#{window_name}'
```

在任何输入之前捕获真实画面：

```bash
target="%3"
tmux -S "$socket_path" capture-pane -p -J -t "$target" -S -120
tmux -S "$socket_path" display-message -p -t "$target" \
  '#{pane_id}|#{pane_pid}|#{window_name}|#{pane_current_command}|#{pane_current_path}|dead=#{pane_dead}|status=#{pane_dead_status}'
```

名称、标题、命令、路径和窗口索引仅为提示；同一窗口中的拆分 pane 共享 `window_name`。通过 socket 和 `%pane-id` 定位 pane；将 PID 和死亡状态视为诊断信息，在 server 重启、respawn 或布局变化后刷新。

## 恢复部分 send

当 `send` 报告 `text_written_not_submitted` 时，文本可能位于目标 composer 中。不要再次发送整条消息。

1. 捕获 pane 并正向确认待处理的 composer 文本。
2. 如果完整的目标文本存在且目标 CLI 的普通提交键已知，仅发送该键。
3. 如果文本不完整、错误，或 pane 处于确认框或菜单状态，停止操作，让用户检查，或使用该 CLI 已确认的目标特定编辑动作。

正向检查后仅补充提交键的恢复：

```bash
tmux -S "$socket_path" capture-pane -p -J -t "$target" -S -40
tmux -S "$socket_path" send-keys -t "$target" Enter
```

`submitted_state_unknown` 意味着 tmux 可能已经投递了文本和提交键。读取 pane；绝不要自动重放。

对于普通 shell 或已正向确认的空 Agent composer，使用与[手工粘贴正文](#手工粘贴正文)相同的 buffer 粘贴机制。`send-keys -l` 路径可能截断长正文。任何此类手工步骤都不属于正常 Skill 工作流，也不持有共享 pane 锁。不要与 `with-agents` 并发运行。

## 手工创建最小后端

`launch` 通常会为你启动缺失的 detached server。当需要单独诊断 tmux 本身时，在其自身的显式 socket 上创建一个最小的测试 session，使其绝不与正在调查的 server 混淆，并保持个人配置不变：

```bash
recovery_socket="/tmp/with-agents-recovery-$$.sock"
session="with-agents-recovery"
tmux -S "$recovery_socket" new-session -d -s "$session" -n shell -c "$PWD"
tmux -S "$recovery_socket" list-panes -t "$session" \
  -F '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|#{pane_current_path}'
```

此恢复后端的每个命令都使用同样的 `-S "$recovery_socket"` 驱动；不要回退到默认 server。

不要为此 Skill 下载或覆盖 `~/.tmux.conf`。控制器从不更改 server 级选项或 pane key mode，且提交是纯 buffer 粘贴加普通 `Enter`，因此无需依赖 `extended-keys`、`extended-keys-format=csi-u` 或 `pane_key_mode=Ext 2`。`doctor` 不读取或报告这些选项；如有兴趣自行检查：

```bash
tmux -S "$socket_path" show-options -s -v extended-keys
tmux -S "$socket_path" show-options -s -v extended-keys-format
```

## 手工粘贴正文

`send` 始终通过 buffer 粘贴，因此手工恢复使用相同的机制配合唯一 buffer 名称：

```bash
buffer_name="with-agents-recovery-$$-$(date +%s)"
printf '%s' "$message" | tmux -S "$socket_path" load-buffer -b "$buffer_name" -
tmux -S "$socket_path" paste-buffer -p -b "$buffer_name" -d -t "$target"
tmux -S "$socket_path" capture-pane -p -J -t "$target" -S -40
```

在发送提交键之前检查待处理的 composer。Bracketed-paste 支持来自目标 CLI 自身行为；`paste-buffer -p` 不提供相关运行时证据。

## 安全关闭 pane

在关闭任何内容之前，捕获最终输出并确认精确身份：

```bash
tmux -S "$socket_path" capture-pane -p -J -t "$target" -S -200
tmux -S "$socket_path" display-message -p -t "$target" \
  '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|#{window_name}|dead=#{pane_dead}'
```

仅关闭当前任务创建或用户明确选择的确切 pane：

```bash
tmux -S "$socket_path" kill-pane -t "$target"
```

绝不要将 `kill-server`、`kill-session` 或 `kill-window` 用作宽泛的恢复 shortcut。在外层任务和任何审查工作完成之前，保留仍在执行、等待、重试和用户拥有的 pane。

## 参考导航

- [cli.md](cli.md) — 命令索引、全局选项、JSON 信封和代表性错误码。
- [messaging.md](messaging.md) — 发送头部语法、params 和回复。
- [operation-states.md](operation-states.md) — 本恢复遵循的发送输入阶段和禁止盲重放规则。
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — TARGET 解析、实时窗口名称、路由语法和自目标。
- [presets.md](presets.md) — preset schema、pane 命名和私有 Agent 注册表。
- [adapters.md](adapters.md) — 各 CLI 的清输入和开始新对话差异。
