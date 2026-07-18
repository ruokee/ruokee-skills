# 初始化 tmux 环境

仅在以下情况阅读本参考文档：

- `tmux` 命令缺失；
- 没有运行中的 tmux 服务器；
- 没有适合外部 Agent CLI 的会话；
- 附带的 `tmux-bridge` 脚本需要检查或经授权安装；或
- 用户明确请求 tmux 初始化。

## 目录

- [1. 检查 tmux](#1-检查-tmux)
- [2. 选择或创建会话](#2-选择或创建会话)
- [3. 检查或安装附带的 tmux-bridge](#3-检查或安装附带的-tmux-bridge)
- [4. 创建目标窗口](#4-创建目标窗口)
- [5. 验证环境](#5-验证环境)
- [6. 移交手动连接](#6-移交手动连接)
- [环境边界](#环境边界)

## 1. 检查 tmux

```bash
command -v tmux
tmux -V
```

当 tmux 缺失时，报告依赖项，并根据当前系统、harness 权限和用户意图处理安装事宜。不要仅为本 Skill 下载完整的个人 tmux 配置或覆盖 `~/.tmux.conf` 或 `~/.config/tmux/tmux.conf`。

## 2. 选择或创建会话

当当前 Agent 已在 tmux 内部运行时，默认使用调用方当前会话：

```bash
session="$(tmux display-message -p '#{session_name}')"
caller="${TMUX_PANE:-}"
```

除非用户选择了其他会话或指定了其他位置的 pane，否则在该会话中创建新的 Agent 窗口或分屏。将相关 pane 保持在同一会话中，用户就能通过鼠标、窗口或 pane 选择在它们之间移动。不要仅为了隔离 Agent 创建单独会话；这会要求用户通过 `C-b s` 等方式切换会话。

用户明确选择的 pane 即使属于其他会话也仍然有效。在原处操作它，不要移动或替换它。

当当前 Agent 在 tmux 外部运行时，先检查现有会话：

```bash
tmux list-sessions
```

按以下顺序优先选择：

1. 用户明确选择的会话或 pane；
2. 包含相关或空闲 pane 的合适已有会话；
3. 仅当没有合适的已有会话时，创建一个新的最小分离会话。

仅在必要时创建回退会话：

```bash
session="with-agents"
tmux has-session -t "$session" 2>/dev/null || \
  tmux new-session -d -s "$session" -n agents -c "$PWD"
```

该会话为外部 Agent CLI 提供终端容器。

## 3. 检查或安装附带的 tmux-bridge

本 Skill 相对于已安装的 Skill 根目录附带 `scripts/tmux-bridge`。解析实际的根目录，不要假定仓库布局：

```bash
bundled_bridge="<skill-root>/scripts/tmux-bridge"
bash -n "$bundled_bridge"
"$bundled_bridge" version
```

无需安装即可直接运行附带的可执行文件。请求使用 `tmux-bridge` 本身不代表已授权将其复制到 `PATH`。

安装脚本会修改用户文件系统，必须先取得用户明确授权。询问授权前，报告：

- 确切的源路径和目标路径；
- 目标是否已经存在、是否会被覆盖；
- 目标目录是否已经在 `PATH` 中。

用户本地的常规目标位置是 `$HOME/.local/bin/tmux-bridge`。获得明确授权后，且目标不需要单独的覆盖授权时，使用以下命令安装到该位置：

```bash
install_dir="${HOME}/.local/bin"
install_target="${install_dir}/tmux-bridge"
install -d "$install_dir"
install -m 0755 "$bundled_bridge" "$install_target"
"$install_target" version
```

如果 `install_target` 已存在且与附带脚本不同，必须取得覆盖该确切文件的明确授权。不要将其作为一般安装授权的一部分替换。没有单独的明确授权，不要编辑 shell 启动文件或修改 `PATH`；当目标目录无法被发现时，直接使用脚本路径。

当 tmux 服务器可用时，针对该服务器验证已安装或直接运行的命令：

```bash
"$bundled_bridge" doctor
```

使用 bridge 与 pane 交互前，阅读 [tmux-bridge.md](tmux-bridge.md)。

## 4. 创建目标窗口

确认请求的可执行文件及其本地参数：

```bash
agent_cli="<requested-cli>"
command -v -- "$agent_cli"
"$agent_cli" --help
```

在选定的会话中创建 shell 窗口并捕获其 pane ID：

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

`split-window` 需要一个已有的目标 pane。当调用方在 tmux 外部时，优先在选定的已有会话中使用 `new-window`。记录当前交互创建的 pane 和窗口，以便将清理范围限制在本次交互创建的资源。

继续阅读 [tmux.md](tmux.md)，通过输入一个 `launch_command` 来启动 CLI；该命令只能由可执行文件以及本地 `--help` 确认的参数构成。

## 5. 验证环境

```bash
tmux list-panes -a \
  -F '#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_current_command}\t#{pane_current_path}'
tmux capture-pane -p -J -t "$target" -S -50
```

确认目标 shell 已在预期的工作目录中就绪，然后继续阅读 [tmux.md](tmux.md) 中的交互工作流。

## 6. 移交手动连接

当用户希望观察或接管时，提供：

```bash
tmux attach-session -t "$session"
```

不要由 tmux 会话外部的 Agent 运行这个会阻塞的 attach 命令。继续使用 `capture-pane` 和 `send-keys` 进行自动化交互。

## 环境边界

- 当调用方在 tmux 外部时，没有 `$TMUX_PANE` 回复地址。直接读取目标 pane。
- 安装附带脚本、覆盖已有可执行文件和修改 shell 配置是彼此独立的状态变更；每项都需要相应的明确授权。
- 用户明确选择的 pane 可能位于其他会话中。无需强制迁移会话，直接复用它。
