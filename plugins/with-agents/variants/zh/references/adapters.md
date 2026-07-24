# 各 CLI 的输入差异

本参考文档收集 Agent 在驱动 CLI 时所需的少量输入知识：如何提交输入、哪个键清除其 composer、以及如何开始新对话。控制器以相同通用方式驱动所有 CLI——粘贴正文、按下 Enter、返回最新画面。下面的备注给出通用默认值；控制器不逐 CLI 验证，因此请根据实际画面确认每一项。配置注册属于 [presets.md](presets.md)；消息流属于 [messaging.md](messaging.md)。

## 目录

- [控制器对 CLI 的了解](#控制器对-cli-的了解)
- [提交输入](#提交输入)
- [清空当前输入](#清空当前输入)
- [开始新对话](#开始新对话)
- [参考导航](#参考导航)

## 控制器对 CLI 的了解

`send` 和 `key` 以相同方式驱动所有 CLI：粘贴正文、按下 Enter、返回最新画面。输入是否按预期送达由**你**从返回的画面判断——读取并决定，就像在原生 tmux 上一样。

唯一重要的各 CLI 知识是 Agent 正确操作所需的内容：哪个键清除 CLI 的 composer，以及如何重置 session。控制器不逐 CLI 跟踪这些信息，因此将下面的备注视为值得一试的通用默认值，并根据实际画面确认。

## 提交输入

普通 Enter 在 Codex、Pi 和 Claude 的默认键映射中提交。对每个正文，`send` 执行一次 `load-buffer` + `paste-buffer -p` 并按下一次 Enter。单行正文提交一次。多行正文是否保持为一个 composer 值取决于目标 CLI 的 bracketed-paste 支持：Codex、Pi 和 Claude 在其默认键映射中会将粘贴的多行正文作为一个值保留，但通用或未知 CLI 可能将内嵌换行视为一次提交，因此读取返回的画面确认正文未被拆分。参见 [messaging.md](messaging.md)。

`send` 无条件按下 Enter；它不知道也不检查正在运行哪个 CLI。如果用户已重新映射 Enter，读取返回的画面——控制器无法检测自定义键映射，仅报告 tmux 接受了按键。

## 清空当前输入

要在键入前清空 composer，先 `read`，然后使用 `key` 发送 CLI 自身的清除键，再 `read` 确认清空：

- 大多数行编辑 composer 使用 `C-u` 清除当前行；
- 要放弃正在进行的轮次，`C-c` 可中断许多 CLI；
- 某些 CLI 使用 `Escape` 清除或取消 composer。

```bash
"$wa" read cx-worker
"$wa" key cx-worker -- C-u
"$wa" read cx-worker
```

从画面确认——CLI 未绑定的键会被静默忽略。

## 开始新对话

要开始新对话或清除上下文，使用 CLI 自身的重置命令搭配 `send --no-header`；斜杠命令会按原样到达 CLI，不带 with-agents 头部：

```bash
"$wa" send cx-worker --no-header -- /new
"$wa" send cx-worker --no-header -- /clear
```

发送下个任务前读取结果画面。重置通常会返回启动画面或空 composer，请根据画面确认 composer 是否就绪。

## 参考导航

- [cli.md](cli.md) — 命令索引、全局选项、JSON 信封和代表性错误码。
- [messaging.md](messaging.md) — 发送头部语法、params、输入队列和回复。
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — TARGET 解析、实时窗口名称、路由和 launch/wait/close。
- [presets.md](presets.md) — preset schema、pane 命名和私有 Agent 注册表。
- [operation-states.md](operation-states.md) — 发送输入阶段和禁止盲重放规则。
- [tmux-recovery.md](tmux-recovery.md) — 控制器无法完成操作时的原生 tmux 恢复。
