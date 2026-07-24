# with-agents CLI 合同

本参考文档涵盖调用模型、全局选项、按使用频率排序的命令索引、JSON 信封和代表性错误索引。每个命令的深层行为位于下方链接的专用参考文档中；本文件不重述那些合同。

## 目录

- [调用方式与全局选项](#调用方式与全局选项)
- [命令索引](#命令索引)
- [JSON 信封](#json-信封)
- [代表性错误码](#代表性错误码)
- [参考导航](#参考导航)

## 调用方式与全局选项

从已安装 Skill 根目录调用可执行文件：

```bash
wa="<skill-root>/scripts/with-agents"
"$wa" <command> ...
```

控制器是一个纯标准库 Python 文件加 tmux。需要 Python 3.10+ 和 tmux 3.2+，由 `doctor` 报告。使用 `with-agents --version` 报告控制器版本。

全局选项可出现在命令之前或紧跟命令之后：

| 选项 | 含义 |
| --- | --- |
| `--json` | 输出机器可读信封 |
| `--socket PATH` | 使用此精确 tmux socket 覆盖 socket 选择 |

在 tmux 内，控制器从 `$TMUX` 继承精确 socket。在 tmux 外，除非提供 `--socket`，否则使用默认 server。当没有 server 存在时，`launch` 可能启动一个最小的 detached session，名为 `with_agents`（使用下划线，以免与 `with-agents:` 路由方案混淆）。无法解析 caller 且存在多个 session 时，必须提供 `--session` 或 `--split`。

`WITH_AGENTS_RUNTIME_DIR` 和 `WITH_AGENTS_CONFIG_DIR`（或 `--runtime-dir` / `--config-dir`）覆盖运行时和配置根目录用于隔离测试；不要将其指向共享或不受信任的目录。

## 命令索引

命令按使用频率排序。每个命名 pane 的命令都使用相同的 `TARGET` 语法——`%pane-id`、裸的实时 `window_name`、显式的 `session:window.pane` 或 with-agents 路由——以相同方式解析（参见 [panes-and-lifecycle.md](panes-and-lifecycle.md)）。

| 命令 | 单行合同 | 详情 |
| --- | --- | --- |
| `read TARGET [--lines N]` | 捕获当前画面 | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `send TARGET [--no-header] [--request] [--correlation-id ID] [--params JSON] -- MESSAGE` | 粘贴一个完整正文，按下 Enter，返回最新画面 | [messaging.md](messaging.md), [operation-states.md](operation-states.md) |
| `list [--detail]` | 列出 pane，含稳定目标、进程提示、路径、实时名称和含规范化 socket 的完整路由；`--detail` 添加修复诊断信息 | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `launch [--cwd DIR] [--no-wait] [--ready-timeout S] [--session S \| --split TARGET] (--preset ... \| -- ARGV...)` | 创建一个 pane 并启动精确 argv，等待可读的启动画面 | [presets.md](presets.md), [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `wait TARGET [--timeout S] [--interval S] [--lines N]` | 等待画面变化或 pane 的进程退出或消失，或直到超时到期 | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `key TARGET -- KEY...` | 发送显式 tmux 按键名并返回最新画面 | [panes-and-lifecycle.md](panes-and-lifecycle.md), [operation-states.md](operation-states.md) |
| `close TARGET [--lines N]` | 捕获最终画面后关闭 pane | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `preset list \| show \| save \| update \| remove` | 管理私有 JSON 启动预设 | [presets.md](presets.md) |
| `doctor` | 报告 Python、tmux、运行时和 Agent 配置诊断 | [presets.md](presets.md) |
| `route [TARGET]` | 打印目标的便携式、socket 限定的路由；无参时打印 caller 自身路由 | [panes-and-lifecycle.md](panes-and-lifecycle.md) |

`MESSAGE`、`ARGV` 和 `KEY` 是普通位置参数。在其前放置 `--`，使 parser 将短横线开头的文本或 argv 作为位置参数内容。运行 `"$wa" <command> --help` 查看精确位置。

`launch` 有三种形式，命名规则因形式而异：

- **Preset：** `launch --preset NAME [--name FULL | --name-suffix SUFFIX]`——名称可选（回退到 preset 的 `pane_name` 或生成的名称）。
- **非 split 直接 argv：** `launch --name FULL -- ARGV...`——`--name` 为必填，因为新窗口需要名称且没有 preset 可回退。
- **Split 直接 argv：** `launch --split TARGET -- ARGV...`——必须省略 `--name`/`--name-suffix`；新 pane 继承目标窗口的实时名称。参见 [presets.md](presets.md)。

## JSON 信封

默认文本输出与 `--json` 使用同一份数据渲染。顶层字段始终按以下顺序出现：

```text
ok, event, stage, target, screen, error, recovery
```

- `ok` 是成功布尔值；进程退出状态与其一致。
- `event` 是命令名称；`stage` 是到达的阶段（例如 `observed`、`submitted`、`listed`、`closed`）。
- `target` 携带 pane、preset、路由或诊断细节；`screen` 携带有界的 `{tail, lines}` 捕获。
- `error` 为 `{code, message[, details]}`（失败时），成功时为 `null`；`recovery` 为单行下一步建议或 `null`。

不适用字段为 `null`。命令特有值位于 `target` 内部；没有第二个顶层信封族。对于 `send`，`target.message` 仅描述控制器构造的输入——它构建的发送者路由、最终 params、关联 ID 以及是否使用了头部。`send` 和 `key` 报告到达的阶段和操作后画面——控制器从不声称它无法证明的字段，如 `delivered` 或 `accepted_by_tui`。

## 代表性错误码

此列表只列出代表性错误码。所属参考文档定义了每个错误码的含义和恢复方法。

| 错误码 | 所属 |
| --- | --- |
| `target_not_found`、`target_ambiguous`、`route_invalid`、`caller_identity_unavailable`、`self_target_denied`、`self_target_unverified`、`target_process_exited` | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `interrupted`、`post_action_observation_failed`、`launch_timeout`、`executable_not_found`、`launch_process_exited` | [operation-states.md](operation-states.md) |
| `params_invalid`、`params_source_conflict` | [messaging.md](messaging.md) |
| `pane_name_source_conflict`、`name_suffix_requires_preset`、`agent_prefix_not_configured`、`invalid_agent_config`、`preset_not_found`、`preset_exists`、`preset_secret_suspected`、`replace_required`、`launch_source_conflict` | [presets.md](presets.md) |
| `tmux_unavailable`、`tmux_timeout`、`tmux_command_failed`、`lock_timeout` | [tmux-recovery.md](tmux-recovery.md) |

`stage` 和 `code` 是不同的概念。`text_not_written`、`text_written_not_submitted`、`submitted_state_unknown`、`key_state_unknown` 以及其余 `*_state_unknown` 值是 `stage` 字段上的**阶段**——描述操作到达了多远的程度。伴随失败操作的 `error.code` 是独立的值：失败的粘贴或提交表现为 `tmux_command_failed`、`tmux_timeout` 或 `interrupted`，并携带相应的部分阶段；操作后捕获失败为 `post_action_observation_failed`。不要将阶段名称当作错误码。完整的阶段与错误码区分参见 [operation-states.md](operation-states.md)。

## 参考导航

- [messaging.md](messaging.md) — 发送头部语法、params、输入队列、操作后快照和回复。
- [operation-states.md](operation-states.md) — 三个技术状态、部分阶段和禁止盲重放恢复。
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — TARGET 解析、实时窗口名称、规范路由、pane 锁、launch/wait/close 和自目标。
- [presets.md](presets.md) — preset 和 `config.json` schema、pane 名称来源、Agent 注册和秘密值守卫。
- [adapters.md](adapters.md) — 各 CLI 的清输入和开始新对话差异。
- [tmux-recovery.md](tmux-recovery.md) — 控制器无法完成操作时的原生 tmux 恢复。
