# Agent 检测与通知适配器

本参考文档负责控制器如何检测 caller Agent、尽力通知策略、composer 识别、`Enter` 语义以及版本诊断。仅在添加或调试 Agent，或分析回调为何注入/未注入时阅读。事件模型和 `reply` 结果属于 [messaging.md](messaging.md)；配置注册属于 [presets.md](presets.md)。

## 目录

- [尽力原则](#尽力原则)
- [检测 caller Agent](#检测-caller-agent)
- [回调的路由身份](#回调的路由身份)
- [通知策略](#通知策略)
- [Composer 识别与危险否决](#composer-识别与危险否决)
- [门铃](#门铃)
- [版本诊断](#版本诊断)

## 尽力原则

结果持久化和唤醒 caller 是两种独立的事实。当 `reply` 发布事件时，结果被持久化存储（`outcome_persisted`）；门铃仅声称一次**尝试**以及底层 tmux 的接受。通知是一种唤醒偏好，绝不是投递保证，也绝不是分发门控。

门铃有目的地注入已验证的 caller 路由——即 request 注册的 caller pane，唤醒它正是其目的。控制器只保留映射到真实破坏性或身份风险的约束：它不会注入到路由身份不再匹配的 pane、前台进程不是已注册 Agent 的 pane，或显示明显危险状态的画面。"未验证"、"较新版本"和"呈现方式变化"**不**是拒绝的理由。（caller 和 child 不能是**同一个** pane 的独立规则在 `request` 分发时执行，而非此处；参见 [messaging.md](messaging.md)。）

## 检测 caller Agent

Adapter 的种类始终由可执行文件解析，而非扫描任务文本，但两种需要种类的上下文从不同的证据中解析。`send`/readiness 检测器（`detect_agent`）优先信任 owned pane 记录的启动 `argv[0]`，仅回退到活跃进程扫描，因为它描述的是该控制器自己启动的进程。回调检测器（`notification_strategy`）有意识地忽略 owned 启动记录——记录在 respawn 后可能过时——并要求**当前活跃前台进程**匹配能力定义或注册表定义；它从不仅凭启动记录注入。在任一上下文中，可执行文件取自进程自身路径或其直接启动器（对 `env`、`node`、`nodejs`、`python`、`python3` 取第一个非选项参数），而仅提及 `codex`、`pi` 或 `claude` 的任务参数不能注册类型。

内置定义（也是内置的 `pane_prefix`）：

| agent_type | pane_prefix | executables |
| --- | --- | --- |
| `codex` | `cx` | `codex` |
| `claude` | `cc` | `claude` |
| `pi` | `pi` | `pi` |

用户可以在 `config.json` 中注册更多 Agent 类型（参见 [presets.md](presets.md)）。注册的精确影响有两个：`preset save/update` 可以记录新的 `agent_type` 并生成 suffix pane 名称；其活跃前台进程与已注册可执行文件匹配的 callback 可以使用**通用**的尽力通知。注册从不授予 Codex/Pi 专用识别器、多行安全性或任何 TUI 接受性声明。

## 回调的路由身份

在回调时，控制器重新解析 caller 路由。通知身份有意识地比 [panes-and-lifecycle.md](panes-and-lifecycle.md) 中的观察身份更窄：它仅比较规范 socket 路径、server PID 和 pane ID。替换的 server 或消失的 pane 会阻止尝试（`caller_identity_mismatch` / `caller_unreachable`）；同一 server 上的相同 pane ID 即使其进程已 respawn 也允许，因为下面的前台进程检查会判定它是否仍是 Agent。Pane PID 和 run ID 仍记录用于诊断，但不是回调的上限。

## 通知策略

路由匹配后，控制器在 caller pane 锁下检查当前前台进程，并选择一种模式：

| 当前前台进程 | 模式 | 行为 |
| --- | --- | --- |
| Codex 或 Pi（内置专用 adapter） | `capability` | 使用专用识别器、稳定延迟和提交策略 |
| 任何其他已注册 Agent——用户添加的**或**内置 Claude——且无专用 adapter | `generic` | 尽力选择加入：一行文本加 `Enter`，标记为 TUI-unverified |
| 不是已注册 Agent（例如回到 shell） | `skip` | 保留 spool，`caller_not_agent`，不注入 |

Generic 模式涵盖每个没有专用 adapter 的已注册 Agent，包括内置的 `claude` 定义，而不仅限用户添加的类型。如果 `config.json` 无效，内置定义仍然可用——内置 Agent 仍可被识别并进入 `capability`（Codex/Pi）或 `generic`（Claude）模式。只有依赖**用户注册的**可执行文件的 callback 会降级为 spool 并附带 `invalid_agent_config` 诊断；这种降级从不会使 `reply` 失败，也不会重新成为分发门控。

在 `capability` 模式下，控制器捕获保留转义的画面并分类 composer：

| 状态 | 动作 |
| --- | --- |
| `idle` | 键入一条门铃，等待稳定延迟，发送 `Enter`（`submit_key`） |
| `busy_queueable` | 键入一条门铃，发送 `Enter`（`busy_key`）；在下一个安全边界投递，而非任务完成时 |
| `unsafe` | 保留 spool，`unsafe_callback_state`，不注入 |
| `unknown` | 保留 spool，`unknown_callback_state`；缺失危险文本不是就绪的证据 |

Generic 模式发送一行文本加 `Enter`，不进行 composer 分类；目标静默丢弃或非破坏性解释该 `Enter` 是可接受的静默失败。

## Composer 识别与危险否决

识别是每个 adapter 的正向检测，绝不是危险模式的补集——未命中危险模式不能反推安全：

- **Codex** 仅从完全空的提示行或其暗色样式占位行接受空 composer，基于 SGR **语义**（dim vs. 真实文本）解析，而非固定的转义字节轮廓。不改变输入语义的前景色/背景色和重置变化可容忍——包括 Codex 0.145 背景色占位行。包含真实键入文本的提示行标记为 `unsafe`。附近的忙碌标记标记为 `busy_queueable`。
- **Pi** 将真实空 composer 识别为最终水平边框对内部的空白行。非空的带边框 composer 标记为 `unsafe`；该边框上方的 `Working` 旋转指示器标记为 `busy_queueable`。

危险模式（权限确认、单键选择、"press Enter"、已有的真实输入）**仅为否决项**：它们可以强制 `unsafe`，但绝不会将 `unknown` 提升为安全。

## 门铃

控制器管理的门铃是一个不含控制字符的单行文本：

```text
[with-agents reply request=<id> seq=<n> status=<status>] <message> [file=<managed-path>]
```

每个发布的事件最多进行一次门铃尝试。失败的回调、被中断的进程或缺失的通知诊断不会重试，也不会阻止后续事件各自进行自己的尝试。并发的门铃可能按 `seq` 乱序显示；权威顺序始终是持久化事件的 `seq`——当需要精确顺序时使用 `inbox <request-id>`。选择自己传输方式（直接 pane 消息、CLI 原生通知）的 child 可以使用自由文本，无需复制此格式。

## 版本诊断

CLI `--version`、正向测试的版本和 tmux extended-key 状态仅用于诊断，由 `doctor`（`checks.notification`）呈现，`version_gate: false`。失败或未知的版本查询从不阻止分发或回调，磁盘上的可执行文件更新也不等于运行的 pane 进程发生了变化。当前的正向测试参考版本为 Codex `0.145.x` 和 Pi `0.80.x`，但更高的版本不会因版本原因被拒绝。

版本门控也无法检测用户自定义的 `Enter` 键映射。Adapter 假定默认的普通 `Enter` steering。`Enter` 不会逐字节中断正在执行的 tool：tmux 将其写入 caller 的 PTY，caller 在下一个安全的 tool-call 或 turn 边界消费它，无需等待外层 goal 结束。依赖完成的后续按键（Codex `Tab`、Pi `Alt+Enter`/`M-Enter`）未被使用，因为它们可能延迟到 goal 完成后才送达——对 prompt 门铃而言为时已晚。如果特定版本的 `Enter` 被证明会导致明确的错误行为，请在代码中记录一个狭窄的 `known_incompatible` 注释并附上证据；不存在"拒绝所有高于最后测试版本的版本"的上限。
