# Agent Pane 的 tmux 操作

本参考用于 `with-agents` 通过原生 tmux 操作 Agent pane。仅在 tmux 缺失、首次设置服务器或初始化会话时使用 [tmux-setup.md](tmux-setup.md)。

## 目录

- [操作规则](#操作规则)
- [目标与发现](#目标与发现)
- [创建会话窗口和 pane](#创建会话窗口和-pane)
- [复用 pane 与身份识别](#复用-pane-与身份识别)
- [启动 Agent CLI](#启动-agent-cli)
- [读取 pane 输出](#读取-pane-输出)
- [发送字面单行输入](#发送字面单行输入)
- [发送多行输入](#发送多行输入)
- [发送特殊按键](#发送特殊按键)
- [回复地址与 pane 标签](#回复地址与-pane-标签)
- [监控与持久等待](#监控与持久等待)
- [清除屏幕、历史和对话上下文](#清除屏幕历史和对话上下文)
- [手动连接与移交](#手动连接与移交)
- [安全清理](#安全清理)
- [故障排查](#故障排查)
- [命令摘要](#命令摘要)

## 操作规则

- 每次交互前立即读取 pane。
- 将字面文本与 Enter 及其他特殊键分开发送。
- 输入或粘贴后再次读取，以确认输入已到达预期字段。
- 在当前 tmux 服务器生命周期内，使用 `%N` pane ID 作为稳定 target。
- 名称、标题、命令和工作目录只能作为身份提示。
- 保持正在执行、等待或重试的 pane 存活。除非用户设置，否则不要应用固定超时。
- 仅在外层用户任务或 goal 完全结束后，关闭当前交互创建的 pane。

只有在发现之后才能设置 target：

```bash
target="%3"
```

在当前服务器中解析出 target 之前，绝不要直接复制示例 target。

## 目标与发现

检查 tmux 并列出会话：

```bash
command -v tmux
tmux -V
tmux list-sessions \
  -F '#{session_name}\t#{session_windows}\t#{session_attached}'
```

列出所有 pane，并显示便于识别的字段：

```bash
tmux list-panes -a \
  -F '#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_title}\t#{pane_current_command}\t#{pane_current_path}\tdead=#{pane_dead}\tpid=#{pane_pid}'
```

常见 target 形式包括：

- pane ID：`%3`；
- 会话、窗口和 pane：`agents:1.0`；
- 窗口 target：`agents:1`，用于需要窗口命令的场景。

优先使用 pane ID 进行自动化操作。窗口或 pane 的数字索引可能在布局变化或清理后改变。

当调用方已经在 tmux 内部运行时，捕获其地址：

```bash
caller="${TMUX_PANE:-}"
session="$(tmux display-message -p '#{session_name}')"
```

在 tmux 外部运行时，`$TMUX_PANE` 为空。不要根据最近活动的 client 推断调用方地址。

## 创建会话窗口和 pane

复用合适的已有会话。仅当没有会话时，才创建一个最小的分离会话：

```bash
session="with-agents"
tmux has-session -t "$session" 2>/dev/null || \
  tmux new-session -d -s "$session" -n agents -c "$PWD"
```

创建窗口并捕获其 pane ID：

```bash
target="$(
  tmux new-window -d -P -F '#{pane_id}' \
    -t "${session}:" \
    -n "$window_name" \
    -c "$working_directory"
)"
```

当需要让已有 pane 与新 pane 并排显示时，创建分屏：

```bash
target="$(
  tmux split-window -d -P -F '#{pane_id}' \
    -t "$caller" \
    -c "$working_directory"
)"
```

当调用方在 tmux 外部，或单独的生命周期更清晰时，使用 `new-window`。记录当前交互是否创建了该 pane；清理操作取决于这一事实。

## 复用 pane 与身份识别

复用 pane 前，捕获其最新屏幕并检查进程状态：

```bash
tmux capture-pane -p -J -t "$target" -S -80
tmux display-message -p -t "$target" \
  '#{pane_id}\t#{pane_title}\t#{pane_current_command}\t#{pane_current_path}\tdead=#{pane_dead}\tpid=#{pane_pid}'
```

当 pane 与当前对话或外层任务有关、用户明确选择了它，或已明确处于空闲状态时，尝试复用。Agent 正在执行、等待或重试的 pane 属于活跃状态，不算空闲。继续该交互，而不是启动重复进程。

除非用户明确请求，否则不要将无关的活跃工作改作他用。如果 pane 的身份或状态仍不确定，则创建新的 pane。

可以选择为 pane 设置标题，以便发现，而不改变全局 tmux 配置：

```bash
tmux select-pane -t "$target" -T "$label"
```

并非所有布局都会显示 pane 标题；标题仍然只是提示，不能作为权威身份。

## 启动 Agent CLI

在本地确认可执行文件和参数：

```bash
agent_cli="<requested-cli>"
command -v -- "$agent_cli"
"$agent_cli" --help
```

仅根据已确认的可执行文件和启动参数构建 `launch_command`。然后遵循读取、字面输入、确认和 Enter 的顺序：

```bash
tmux capture-pane -p -J -t "$target" -S -50
tmux send-keys -t "$target" -l -- "$launch_command"
tmux capture-pane -p -J -t "$target" -S -20
tmux send-keys -t "$target" Enter
```

等待 CLI 输入界面出现，并在发送任务前读取它。

## 读取 pane 输出

读取最近的合并输出：

```bash
tmux capture-pane -p -J -t "$target" -S -200
```

有用的选项包括：

- `-p`：将捕获的内容打印到 stdout；
- `-J`：合并换行的内容并保留逻辑终端行；
- `-S -200`：从可见 pane 上方 200 行处开始；
- `-E <line>`：在需要限定范围时设置明确的结束行；
- `-e`：仅当使用者确实需要时保留转义序列。

捕获的文本是终端屏幕快照。它可能包含过期的 scrollback、被覆盖的进度行、待发送的输入，或与活跃进程并列的已完成结果。应判断 TUI 状态，而不是把最后一行当作结构化完成标志。

## 发送字面单行输入

每条单行消息都使用以下完整循环：

```bash
tmux capture-pane -p -J -t "$target" -S -50
tmux send-keys -t "$target" -l -- "$message"
tmux capture-pane -p -J -t "$target" -S -20
tmux send-keys -t "$target" Enter
```

`send-keys -l` 发送字面字符，而不是解析按键名称。保持与 `Enter` 分离，以便中间的 capture 确认 target、输入字段和待发送文本。

终端更新可能会异步到达。如果中间的 capture 只显示了部分待输入文本，则继续读取，直到完整输入可见。在验证完成前，不要重新输入消息，也不要发送 Enter。

不要把不受信任的任务文本放入 shell 命令字符串。仅在 Agent CLI 就绪后输入它。

## 发送多行输入

使用唯一命名的 tmux buffer 和 bracketed paste：

```bash
buffer="with-agents-$$-$(date +%s)"
printf '%s' "$message" | tmux load-buffer -b "$buffer" -
tmux paste-buffer -p -b "$buffer" -d -t "$target"
tmux capture-pane -p -J -t "$target" -S -30
tmux send-keys -t "$target" Enter
```

当目标应用请求该模式时，`paste-buffer -p` 会用 bracketed-paste 控制序列包裹 payload。成功粘贴后，`-d` 会删除命名 buffer。

粘贴后，确认整个请求仍是一个待发送的输入，再发送 Enter。并发交互之间不要使用固定的 buffer 名称。不要使用 `send-keys` 重复发送原始换行；兼容的 TUI 可能会将其解析为多次提交。

当目标不支持 bracketed paste 时，检查其本地帮助，并使用其文档说明的多行编辑器或文件输入机制。

## 发送特殊按键

发送特殊按键时不要使用 `-l`：

```bash
tmux send-keys -t "$target" Enter
tmux send-keys -t "$target" Escape
tmux send-keys -t "$target" C-l
```

发送任何特殊键之前，都要读取 pane 并确认预期效果。将 `C-c`、`C-d`、进程终止和 TUI 退出键视为破坏性控制：

```bash
tmux send-keys -t "$target" C-c
```

仅当用户请求终止，或有充分证据表明进程无法继续且无法在范围内恢复时，才使用这些按键。不要打断短期错误、自动重试或暂时静默。

## 回复地址与 pane 标签

当调用方在 tmux 内部运行时，使用回复地址包装请求：

```bash
caller="${TMUX_PANE:-}"
if [ -n "$caller" ]; then
  message="[with-agents from:${caller}] ${request}"
else
  message="$request"
fi
```

收到 `[with-agents from:%3]` 这类消息时，解析 `%3`，读取它，将回复以字面文本输入，确认后再单独发送 Enter。

当调用方在 tmux 外部运行时，不要虚构回复 target。以适中的间隔读取 Agent pane 来收集响应。

## 监控与持久等待

同时读取 pane 屏幕和 tmux 进程元数据：

```bash
tmux capture-pane -p -J -t "$target" -S -120
tmux display-message -p -t "$target" \
  'dead=#{pane_dead}\tstatus=#{pane_dead_status}\tcommand=#{pane_current_command}\tpid=#{pane_pid}'
```

使用适中的观察间隔。区分以下状态：

- 有活跃输出或实时进度：继续等待；
- 暂时性错误后的自动重试：允许重试并保留 pane；
- Agent 问题或授权提示：回复它，或在保留 pane 的同时询问用户；
- goal 阻塞：先提供上下文或在范围内恢复，再报告；
- Agent 请求已完成但交互式 CLI 仍然打开：保留 pane 以便后续工作；
- 进程已退出或 pane 已死亡：在决定是否可以恢复之前，捕获最终输出和状态。

除非用户设置，否则不要使用固定超时或重试次数。暂时静默不代表失败。

## 清除屏幕、历史和对话上下文

这些操作含义不同：

```bash
tmux send-keys -t "$target" C-l
tmux clear-history -t "$target"
```

- `C-l` 通常会重绘或清除 shell/TUI 屏幕；具体行为取决于前台应用。
- `clear-history` 会移除 pane 的 tmux scrollback。
- 两种操作都不会清除 Agent CLI 对话、模型上下文或持久化会话。

要获得新的 Agent 上下文，仅使用该 CLI 本地 `--help` 或命令界面确认过的清除、重置或新建对话机制。操作前后都读取 pane。如果没有安全的重置方式，则正常退出已完成的 CLI，并在同一个可复用 pane 中重新启动。

## 手动连接与移交

为用户提供用于观察或接管的会话 target：

```bash
tmux attach-session -t "$session"
```

对于 tmux 外部的调用方，连接会阻塞。不要将其作为自动化观察方法运行；继续使用 `capture-pane` 和 `display-message`。

对于特定 target，还要报告 pane ID 以及 `list-panes` 输出中的 `session:window.pane` 地址。

## 安全清理

清理前，捕获最终输出并确认所有权：

```bash
tmux capture-pane -p -J -t "$target" -S -200
tmux display-message -p -t "$target" \
  '#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_current_command}\tdead=#{pane_dead}'
```

只有在以下条件全部满足时，才关闭 pane：

- 当前交互创建了它；
- 外层用户任务或 goal 已完全结束，或用户明确请求终止；
- 不再需要移交、后续工作、修改、审查或可恢复的重试。

然后明确指定记录的 pane ID：

```bash
tmux kill-pane -t "$target"
```

关闭最后一个 pane 也会移除其窗口。除非用户明确请求更大的范围且所有权已确认，否则绝不要关闭预先存在的用户 pane。只有在用户明确请求该更大范围且所有权确定时，才使用 `kill-window`、`kill-session` 或 `kill-server`。

## 故障排查

### `can't find pane`

刷新 `list-panes -a`；pane 可能已经退出，或服务器可能已经重启。不要复用过期的 `%N` target。

### 文本到达了错误的 pane 或字段

在发送 Enter 前停止。捕获 pane，修正 target，并仅使用与可见 TUI 相适应的按键移除待输入文本。不要假定 shell 编辑快捷键适用于所有 TUI。

### 多行文本被提交成多个请求

确认使用了 `paste-buffer -p`，并且目标支持 bracketed paste。如果不支持，使用 CLI 文档说明的多行机制。

### 重试似乎卡住

以适中的间隔读取最近输出和进程元数据。提供所请求的反馈或授权。不要仅因进程安静就杀掉或复制一个活跃进程。

### 清屏没有重置 Agent

这是预期行为：tmux 屏幕和历史控制不会重置模型上下文。使用已确认的 Agent CLI 对话命令。

## 命令摘要

| 意图 | 命令 |
| --- | --- |
| 列出会话 | `tmux list-sessions` |
| 列出所有 pane | `tmux list-panes -a -F '<format>'` |
| 读取输出 | `tmux capture-pane -p -J -t "$target" -S -200` |
| 检查 pane 状态 | `tmux display-message -p -t "$target" '<format>'` |
| 输入字面文本 | `tmux send-keys -t "$target" -l -- "$message"` |
| 提交输入 | `tmux send-keys -t "$target" Enter` |
| 粘贴多行文本 | `tmux paste-buffer -p -b "$buffer" -d -t "$target"` |
| 创建窗口 | `tmux new-window -d -P -F '#{pane_id}' ...` |
| 创建分屏 | `tmux split-window -d -P -F '#{pane_id}' ...` |
| 标记 pane | `tmux select-pane -t "$target" -T "$label"` |
| 清除 tmux 历史 | `tmux clear-history -t "$target"` |
| 手动连接 | `tmux attach-session -t "$session"` |
| 关闭当前交互创建的 pane | `tmux kill-pane -t "$target"` |
