# with-agents 的 tmux 故障恢复

仅当随附控制器无法完成事件、`doctor` 报告后端问题或需要手工恢复部分输入时，才阅读本文。原生 tmux 会绕过观察凭据、所有权检查、per-pane 锁、argv 记录和结构化的部分阶段报告，请将其作为有意的 fallback 而非正常路径使用。

## 目录

- [诊断 server 与 socket](#诊断-server-与-socket)
- [解析并检查 pane](#解析并检查-pane)
- [恢复部分 send](#恢复部分-send)
- [手工创建最小后端](#手工创建最小后端)
- [恢复多行输入](#恢复多行输入)
- [检查 owned 元数据](#检查-owned-元数据)
- [安全关闭 pane](#安全关闭-pane)

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
tmux list-sessions
```

`$TMUX` 的格式为 `socket_path,server_pid,session_index`。当它指向预期的 live server 时，使用该精确 socket，而非从另一个 client 猜测：

```bash
socket_path="${TMUX%%,*}"
tmux -S "$socket_path" list-sessions
tmux -S "$socket_path" display-message -p '#{socket_path}|#{pid}'
```

如果 `$TMUX` 已过期，不要将输入操作悄悄重定向到默认 server。与用户一起或从一个已知的精确 socket 找到预期的 server，然后以 `--socket PATH` 重新运行控制器命令。

## 解析并检查 pane

列出权威身份及其发现提示：

```bash
tmux list-panes -a \
  -F '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|#{pane_pid}|#{pane_current_command}|#{pane_current_path}|dead=#{pane_dead}|name=#{@with_agents_name}|run=#{@with_agents_run_id}'
```

在任何输入之前捕获真实画面：

```bash
target="%3"
tmux capture-pane -p -J -t "$target" -S -120
tmux display-message -p -t "$target" \
  '#{pane_id}|#{pane_pid}|#{pane_current_command}|#{pane_current_path}|dead=#{pane_dead}|status=#{pane_dead_status}'
```

名称、标题、命令、路径和窗口索引仅为提示。在 server 重启、respawn 或布局变化后刷新 pane ID 和 PID。

## 恢复部分 send

当 `send` 报告 `text_written_not_submitted` 时，文本可能位于目标 composer 中。不要再次发送整条消息。

1. 捕获 pane 并正向确认待处理的 composer 文本。
2. 如果完整的目标文本存在且目标 CLI 的普通提交键已知，仅发送该键。
3. 如果文本不完整、错误，或 pane 处于确认框或菜单状态，停止操作，让用户检查，或使用该 CLI 已确认的目标特定编辑动作。

正向检查后仅补充提交键的恢复：

```bash
tmux capture-pane -p -J -t "$target" -S -40
tmux send-keys -t "$target" Enter
```

`submitted_state_unknown` 意味着 tmux 可能已经投递了文本和提交键。读取 pane；绝不要自动重放。

对于普通 shell 或已正向确认的空 Agent composer，字面单行输入为：

```bash
tmux send-keys -t "$target" -l -- "$message"
tmux send-keys -t "$target" Enter
```

这对手工命令不属于正常 Skill 工作流，也不持有共享控制器锁。不要与 `with-agents` 并发运行。

## 手工创建最小后端

`create` 和 `launch` 通常会为你启动缺失的 detached server。当需要单独诊断 tmux 本身时，创建一个最小的测试 session，而非编辑个人配置：

```bash
session="with-agents-recovery"
tmux new-session -d -s "$session" -n shell -c "$PWD"
tmux list-panes -t "$session" \
  -F '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|#{pane_current_path}'
```

不要为此 Skill 下载或覆盖 `~/.tmux.conf`。控制器从不更改 server 级选项或 pane key mode。Pi 和 Codex pane notification 在安全的 idle 和 busy 状态均使用普通 `Enter`，因此两者都不依赖 `extended-keys`、`extended-keys-format=csi-u` 或 `pane_key_mode=Ext 2`。`doctor` 仍报告 server 的 `extended_keys` 和 `extended_keys_format` 值，但仅作为信息性 tmux 事实，而非 notification 前置条件。如有兴趣自行检查：

```bash
tmux show-options -s -v extended-keys
tmux show-options -s -v extended-keys-format
```

## 恢复多行输入

未知 adapter 有意识地拒绝多行 `send`。当目标 CLI 有独立文档确认了 bracketed-paste 支持且手工恢复在范围内时，使用一个唯一 buffer：

```bash
buffer_name="with-agents-recovery-$$-$(date +%s)"
printf '%s' "$message" | tmux load-buffer -b "$buffer_name" -
tmux paste-buffer -p -b "$buffer_name" -d -t "$target"
tmux capture-pane -p -J -t "$target" -S -40
```

在发送提交键之前检查待处理的 composer。`paste-buffer -p` 不能在运行时证明应用程序支持 bracketed paste；该支持必须来自目标 adapter 或 CLI 自身的文档。

## 检查 owned 元数据

控制器仅在 tmux pane 选项中保存简短的非机密路由元数据：

```bash
tmux show-options -p -t "$target" | \
  grep -E '@with_agents_(owner|run_id|name|preset)'
```

精确的 argv 和观察或 request 状态位于 `doctor` 报告的私有运行时根目录中。不要编辑这些文件来绕过身份或所有权错误。记录不匹配通常意味着 pane 已 respawn、server 已变化或状态已过期——应建立新的观察或启动新的 owned run。

## 安全关闭 pane

在关闭任何内容之前，捕获最终输出并确认精确所有权：

```bash
tmux capture-pane -p -J -t "$target" -S -200
tmux display-message -p -t "$target" \
  '#{pane_id}|#{session_name}:#{window_index}.#{pane_index}|owner=#{@with_agents_owner}|run=#{@with_agents_run_id}|dead=#{pane_dead}'
```

仅关闭当前任务拥有或用户明确选择的确切 pane：

```bash
tmux kill-pane -t "$target"
```

绝不要将 `kill-server`、`kill-session` 或 `kill-window` 用作宽泛的恢复 shortcut。在外层任务和任何审查工作完成之前，保留仍在执行、等待、重试和用户拥有的 pane。
