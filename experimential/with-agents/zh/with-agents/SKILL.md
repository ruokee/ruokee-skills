---
name: with-agents
description: 当用户明确指定特定外部 Agent CLI、已有 Agent pane、tmux 交互或本 Skill 时，通过 tmux 使用外部 Agent CLI。当前 harness 有可用的原生 subagents 时，普通委派优先使用它们。涵盖 CLI 发现、pane 生命周期、字面输入、多行提示、持久等待与重试、反馈处理及安全终止。
---

# 与 Agent 协作（With Agents）

将每个外部 Agent CLI 视为普通的交互式终端程序。通过 tmux 启动、观察和与之交互。

## 选择调用路径

1. 检查当前 harness 暴露的工具。
2. 当 harness 提供原生 subagent、委派或并行 Agent 工具时，将其用于普通委派。
3. 仅当用户明确请求外部 Agent CLI、已有 Agent pane、tmux 交互或 `with-agents` 时，才使用本 Skill。

根据当前请求选择 CLI、模型、工作目录和任务。

## 发现环境

在启动任何内容之前，先检查请求的 CLI 和 tmux：

```bash
agent_cli="<requested-cli>"
command -v -- "$agent_cli"
"$agent_cli" --help
command -v tmux
tmux list-sessions
```

将 `<requested-cli>` 替换为实际的可执行文件。根据已安装 CLI 的 `--help` 输出确认启动参数，不要依赖记忆中的语法。

仅当 tmux 缺失、没有运行中的服务器、没有合适的会话存在或用户明确请求 tmux 初始化时，才阅读 [tmux-setup.md](references/tmux-setup.md)。

## 发现 Agent Pane

列出当前 tmux 服务器中的所有 pane：

```bash
tmux list-panes -a \
  -F '#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_current_command}\t#{pane_current_path}'
```

将 `%N` 格式的 pane ID 用作后续命令的 `target`。仅将窗口名称、pane 标题和当前命令视为发现提示。在发送输入之前先读取 pane 内容，以确认其身份和 TUI 状态：

```bash
tmux capture-pane -p -J -t "$target" -S -50
```

## 复用已有 Pane

创建新 pane 前先检查现有 pane。当 pane 与当前对话或外层任务有关、用户明确指定了该 pane，或 pane 已确认空闲时，优先尝试复用。

先读取 pane 内容。Agent 正在执行、等待或重试的 pane 属于活跃状态，不算空闲；继续观察或与该 Agent 交互，不要启动重复进程。除非用户明确指示，否则不要改作他用仍承载无关活跃工作的 pane。

现有 Agent 上下文仍然相关时，继续同一个 CLI 对话。需要全新上下文时，仅使用目标 CLI 本地帮助或命令界面确认过的清空、重置或新建对话机制。清空终端画面不等于清空对话上下文。无法确认可安全复用时，创建新的 pane。

## 启动新的 Agent CLI

当没有合适的 pane 存在时，在选定的会话中创建一个 shell 窗口并捕获其 pane ID：

```bash
target="$(
  tmux new-window -d -P -F '#{pane_id}' \
    -t "${session}:" \
    -n "$window_name" \
    -c "$working_directory"
)"
```

仅使用可执行文件和本地 `--help` 确认的参数构建 `launch_command`。不要将任务文本放入此 shell 命令。使用与 Agent 消息相同的读取、字面输入、确认和 Enter 规范来启动 CLI：

```bash
tmux capture-pane -p -J -t "$target" -S -50
tmux send-keys -t "$target" -l -- "$launch_command"
tmux capture-pane -p -J -t "$target" -S -20
tmux send-keys -t "$target" Enter
```

根据交互布局选择 `new-window` 或 `split-window`。

## 发送单行请求

遵循读取、输入、确认、然后 Enter 的顺序：

```bash
tmux capture-pane -p -J -t "$target" -S -50
tmux send-keys -t "$target" -l -- "$message"
tmux capture-pane -p -J -t "$target" -S -20
tmux send-keys -t "$target" Enter
```

使用 `-l` 发送字面文本。将文本与 `Enter`、`C-c` 或其他特殊键分开发送。中间步骤读取 pane 内容以确认文本已到达预期的输入字段。

当调用方已在 tmux 内部时，在消息前加上调用方的回复地址：

```bash
caller="${TMUX_PANE:-}"
if [ -n "$caller" ]; then
  message="[with-agents from:${caller}] ${request}"
else
  message="$request"
fi
```

当调用方在 tmux 外部时，不要虚构回复 pane。直接读取目标 pane 来收集响应。

## 发送多行请求

使用当前交互唯一的 buffer 名称：

```bash
buffer="with-agents-$$-$(date +%s)"
printf '%s' "$message" | tmux load-buffer -b "$buffer" -
tmux paste-buffer -p -b "$buffer" -d -t "$target"
tmux capture-pane -p -J -t "$target" -S -20
tmux send-keys -t "$target" Enter
```

使用 `-p`，使 tmux 在目标应用请求 bracketed paste 模式时，用相应控制序列包裹内容。这可防止兼容的 TUI 将内嵌换行视为多次独立提交。粘贴后先确认整段请求仍显示为一条待提交输入，再发送 `Enter`。

不要在并发交互之间复用固定的 buffer 名称。目标 TUI 不支持 bracketed paste 时，先发现其安全的多行输入机制，不要把原始换行作为按键注入。

## 读取、回复和继续

读取 pane 的最新输出：

```bash
tmux capture-pane -p -J -t "$target" -S -200
```

将捕获的输出视为终端屏幕，而非结构化结果、可靠的进度记录或完成信号。在跟进、提供上下文或向用户报告之前，先判断实际的屏幕状态。

当请求包含 `[with-agents from:%3]` 这样的回复地址时，将 `%3` 用作回复目标，并应用相同的读取、字面输入、确认和 Enter 序列。

避免高频轮询。继续执行不冲突的工作，并以适中的间隔或在需要结果时读取 pane。

## 持久等待与恢复

当 Agent 正在运行、等待或重试时，保留目标 pane：

- 将正在执行、等待响应或自动重试的活跃 Agent 进程视为仍在活动中。除非用户明确设置，否则不要强加固定的超时或重试次数。
- 对于短暂的 API、网络、速率限制或上游错误，优先让 Agent 自行重试。不要仅因为短期错误、暂时静默或长时间等待就发送 `C-c`、杀掉 pane 或启动等效的重复进程。
- 以适中的频率读取 pane，以区分自动重试、输入请求、任务完成和进程退出。等待期间仅执行不冲突的工作。
- 当 Agent 请求反馈、澄清或授权时，读取问题并通过相同的读取、输入、确认和 Enter 序列进行回复。如果 Agent 需要用户决策或新增授权，向用户说明该需求并保持 pane 等待。
- 当 Agent 报告 goal 阻塞时，检查原因。首先提供缺失的上下文、回答问题或处理可恢复的情况。如果恢复需要用户输入或外部状态变更，则报告阻塞，同时保留任何活跃或等待中的 Agent。
- 仅当外层用户任务或 goal 已完全结束、用户明确请求终止，或有充分证据表明 Agent 无法继续且无法在授权范围内恢复时，才结束 Agent。结束前捕获最终输出和进程状态。

即使单次 Agent 请求已经返回，也要将当前交互创建的 pane 保留到外层用户任务或 goal 完全结束。将其复用于后续提问、修改、审查或其他 Agent 步骤。完全结束后，捕获最终状态；无需交接或进一步审查时，仅清理当前交互创建的 pane。除非用户明确要求，否则不要关闭预先存在的用户 pane。
