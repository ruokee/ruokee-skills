# 初始化 tmux 环境

仅在以下情况阅读本参考文档：

- `tmux` 命令缺失；
- 没有运行中的 tmux 服务器；
- 没有适合外部 Agent CLI 的会话；或
- 用户明确请求 tmux 初始化。

## 1. 检查 tmux

```bash
command -v tmux
tmux -V
```

当 tmux 缺失时，报告依赖项，并根据当前系统、harness 权限和用户意图处理安装事宜。不要仅为本 Skill 下载完整的个人 tmux 配置或覆盖 `~/.tmux.conf` 或 `~/.config/tmux/tmux.conf`。

## 2. 选择或创建会话

当当前 Agent 已在 tmux 内部运行时，复用当前服务器和会话：

```bash
session="$(tmux display-message -p '#{session_name}')"
caller="${TMUX_PANE:-}"
```

当当前 Agent 在 tmux 外部运行时，先检查现有会话：

```bash
tmux list-sessions
```

当存在合适的会话时复用它。否则创建一个最小的分离会话：

```bash
session="with-agents"
tmux has-session -t "$session" 2>/dev/null || \
  tmux new-session -d -s "$session" -n agents -c "$PWD"
```

该会话为外部 Agent CLI 提供终端容器。

## 3. 创建目标窗口

确认请求的可执行文件及其本地参数：

```bash
agent_cli="<requested-cli>"
command -v -- "$agent_cli"
"$agent_cli" --help
```

创建一个 shell 窗口并捕获其 pane ID：

```bash
target="$(
  tmux new-window -d -P -F '#{pane_id}' \
    -t "${session}:" \
    -n "$window_name" \
    -c "$working_directory"
)"
```

当并排观察更有用时，改用 split 方式创建：

```bash
target="$(
  tmux split-window -d -P -F '#{pane_id}' \
    -t "$caller" \
    -c "$working_directory"
)"
```

`split-window` 需要一个已有的目标 pane。当调用方在 tmux 外部时，默认使用 `new-window`。

继续阅读 [tmux.md](tmux.md)，通过输入一个仅由可执行文件和本地 `--help` 确认的参数构成的 `launch_command` 来启动 CLI。

## 4. 验证环境

```bash
tmux list-panes -a \
  -F '#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_current_command}\t#{pane_current_path}'
tmux capture-pane -p -J -t "$target" -S -50
```

确认目标 shell 已在预期的工作目录中就绪，然后继续阅读 [tmux.md](tmux.md) 中的交互工作流。

## 5. 移交手动连接

当用户希望观察或接管时，提供以下命令：

```bash
tmux attach-session -t "$session"
```

不要由当前 session 外部的 Agent 运行这个会阻塞的 attach 命令。继续使用 `capture-pane` 和 `send-keys` 进行自动化交互。

## 环境边界

- 当调用方在 tmux 外部时，没有 `$TMUX_PANE` 回复地址。直接读取目标 pane。
