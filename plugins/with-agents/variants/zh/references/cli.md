# with-agents CLI 合同

`cli.md` 参考文档涵盖调用模型、全局选项、精确的命令索引、冻结的 JSON 信封和具有代表性的错误码索引。每个命令的深层行为位于下面索引链接的专用参考文档中；本文件不重述那些合同。

## 目录

- [调用方式与全局选项](#调用方式与全局选项)
- [命令索引](#命令索引)
- [JSON 信封](#json-信封)
- [具有代表性的错误码](#具有代表性的错误码)
- [各合同的对应位置](#各合同的对应位置)

## 调用方式与全局选项

从已安装 Skill 根目录调用可执行文件：

```bash
wa="<skill-root>/scripts/with-agents"
"$wa" <command> ...
```

控制器是一个纯标准库 Python 文件加 tmux。需要 Python 3.10+ 和 tmux 3.2+，由 `doctor` 报告。`scripts/launch-agent` 完全等价于 `scripts/with-agents launch`，接受相同选项。

全局选项可出现在命令之前或紧跟命令之后：

| 选项 | 含义 |
| --- | --- |
| `--json` | 输出机器可读信封而非渲染文本 |
| `--socket PATH` | 使用此精确 tmux socket 而非 `$TMUX` 或默认 server |
| `--caller-id ID` | 为在 tmux 外并发运行的多个调用者保持观察凭据和 caller 路由身份区分 |

在 tmux 内，控制器从 `$TMUX` 继承精确 socket。在 tmux 外，除非提供 `--socket`，否则使用默认 server。当没有 server 存在时，`create` 和 `launch` 可能启动一个最小的 detached `with-agents` session。当 caller session 无法解析且有多个 session 存在时，需要 `--session` 或 `--split` 而非猜测。

`WITH_AGENTS_RUNTIME_DIR` 和 `WITH_AGENTS_CONFIG_DIR` 覆盖运行时和配置根目录用于隔离测试；不要将其指向共享或不受信任的目录。

## 命令索引

| 命令 | 单行合同 | 详情 |
| --- | --- | --- |
| `list` | 列出 pane，含稳定目标、进程提示、路径、所有权、名称和 run ID | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `read TARGET [--lines N]` | 捕获当前画面并记录 caller 作用域的观察 | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `create --name NAME [--cwd DIR] [--session S \| --split TARGET]` | 创建 owned shell pane 并观察 | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `launch [--cwd DIR] [--session S \| --split TARGET] (--preset NAME [--name FULL \| --name-suffix SUFFIX] \| --name FULL -- ARGV...)` | 创建 owned pane 并启动精确 argv | [presets.md](presets.md), [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `send TARGET [--allow-foreign] MESSAGE` | 写入一条完整消息及其提交键 | [messaging.md](messaging.md), [operation-states.md](operation-states.md) |
| `key TARGET [--allow-foreign] KEY...` | 观察后发送显式 tmux 按键名 | [panes-and-lifecycle.md](panes-and-lifecycle.md), [operation-states.md](operation-states.md) |
| `wait TARGET [--timeout S] [--interval S] [--lines N]` | 等待一次画面或进程变化，或等待超时到期 | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `restart TARGET [--force-foreign] (--preset NAME \| -- ARGV...)` | 在原位 respawn pane，赋予新的运行身份 | [panes-and-lifecycle.md](panes-and-lifecycle.md), [operation-states.md](operation-states.md) |
| `close TARGET [--lines N] [--force-foreign]` | 捕获最终画面后关闭 pane | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `request TARGET [--allow-foreign] [--notify spool\|pane] [--reply-to TARGET [--reply-socket PATH]] [--reply-ttl SECONDS] MESSAGE` | 分发任务并打开异步结果流 | [messaging.md](messaging.md) |
| `reply REQUEST_ID --status progress\|question\|done\|blocked\|failed [--message M] [--file PATH]` | 追加一个结果事件并可选择响铃 caller | [messaging.md](messaging.md) |
| `inbox [REQUEST_ID]` | 列出 caller 的有事件 request，或单个 request 的完整事件流 | [messaging.md](messaging.md) |
| `preset list \| show \| save \| update \| remove` | 管理私有 JSON 启动预设 | [presets.md](presets.md) |
| `gc [--stale [DAYS]] [--delete-stale]` | 删除已终结 request 的临时状态，或检查显式过时 request | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `doctor` | 报告 Python、tmux、运行时、通知 adapter 和 Agent 配置诊断 | [adapters.md](adapters.md) |
| `version` | 报告控制器版本 | — |

`MESSAGE`、`ARGV` 和 `KEY` 是普通位置参数。在其前放置 `--`，确保以短横线开头的文本或 argv 不被当作选项。运行 `"$wa" <command> --help` 查看精确位置。

## JSON 信封

默认文本输出与 `--json` 使用同一份数据渲染。顶层字段始终按以下顺序出现：

```text
ok, event, stage, target, request, notification, screen, error, recovery
```

- `ok` 是成功布尔值；进程退出状态与其一致。
- `event` 是命令名称；`stage` 是到达的阶段（例如 `observed`、`submitted`、`outcome_persisted`、`listed`、`closed`）。
- `target` 携带 pane、preset 或诊断细节；`request` 携带 request/event/inbox 细节；`notification` 携带门铃诊断；`screen` 携带有界的 `{tail, lines}` 捕获。
- `error` 为 `{code, message[, details]}`（失败时），成功时为 `null`；`recovery` 为单行下一步建议或 `null`。

不适用字段为 `null`。命令特有值位于对应的 `target` 或 `request` 对象中；不添加第二个顶层信封族。文本和按键结果报告 `tmux_accepted` 和 `tui_acceptance: "unverified"`——控制器从不声称它无法证明的字段，例如 `delivered` 或 `accepted_by_tui`。

## 具有代表性的错误码

此列表具有代表性，并非穷举枚举。所属参考文档定义了每个错误码的含义和恢复方法。

| 错误码 | 所属 |
| --- | --- |
| `observation_required`、`observation_expired`、`target_identity_changed`、`foreign_write_denied`、`self_target_denied`、`target_process_exited`、`foreign_restart_denied`、`foreign_close_denied` | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `submitted_state_unknown`、`key_state_unknown`、`multiline_not_safe`、`interrupted` | [operation-states.md](operation-states.md) |
| `pane_name_source_conflict`、`name_suffix_requires_preset`、`agent_prefix_not_configured`、`invalid_agent_config`、`preset_not_found`、`preset_exists`、`preset_secret_suspected`、`replace_required`、`launch_source_conflict` | [presets.md](presets.md) |
| `reply_ticket_invalid`、`reply_stream_terminated`、`reply_event_limit`、`reply_result_budget_exhausted`、`reply_ticket_expired`、`already_replied`、`reply_route_invalid`、`invalid_reply_ttl`、`result_file_invalid`、`result_file_too_large` | [messaging.md](messaging.md) |
| `notify_prerequisite_missing`、`tmux_unavailable`、`tmux_timeout`、`tmux_command_failed`、`lock_timeout` | [messaging.md](messaging.md)、[adapters.md](adapters.md)、[tmux-recovery.md](tmux-recovery.md) |

并非每个 `stage` 都是错误码。`text_not_written`、`text_written_not_submitted` 和生命周期 `*_state_unknown` 值是 `send`/变更操作的**部分阶段**，报告在信封的 `stage` 字段上；其中一些（`submitted_state_unknown`、`key_state_unknown`）在操作在该点失败时也是稳定的错误码。完整的阶段与错误码区分参见 [operation-states.md](operation-states.md)。

## 各合同的对应位置

- [presets.md](presets.md) — preset 和 `config.json` schema、pane 名称来源、Agent 注册、秘密值守卫。
- [messaging.md](messaging.md) — `send` 以及 `request`/`reply`/`inbox` 异步事件流。
- [operation-states.md](operation-states.md) — 每个原子操作的部分阶段和禁止盲重放恢复。
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — 身份、观察、所有权、锁、`gc` 和 pane 生命周期命令。
- [adapters.md](adapters.md) — Agent/启动器检测、通知策略、composer 识别、版本诊断。
- [tmux-recovery.md](tmux-recovery.md) — 控制器无法完成事件时的原生 tmux 恢复。
