# Changelog

## 0.3.0 - 2026-07-24

### 变更

- 将 pane TARGET 统一为 `%pane-id`、实时 `window_name`、`session:window.pane` 或 canonical with-agents route；route 始终携带 name、decimal pane ID 和 canonical absolute socket，不再绑定 server/pane PID generation，也不保留 socketless route 兼容分支。
- public `name` 改为从 tmux vis 表示还原的实时 `window_name`；控制字符和 Unicode 行/段分隔符在 route 中回退为 `pane-<id>`。普通结果与 `list --detail` 使用同一种完整 route，detail 只增加诊断字段。
- `$TMUX` 从右侧解析固定的 server PID 与 session index，保留 socket path 中的逗号；raw tmux recovery 的后续命令始终复用同一个 explicit socket。
- `send` 默认添加发送方 route header；`--request`、`--correlation-id` 与严格 `{string: string}` 的 `--params` 统一承载回复意图和关联信息。回复改为向 header route 执行普通 `send`。
- `send` 对所有正文使用一次 `paste-buffer -p` 加一次 Enter，并在释放 pane lock 后返回动作后 snapshot；同一 pane 的 controller 操作串行，不检查目标是否 idle。目标级多行提交语义取决于 bracketed-paste 支持。
- `launch` 默认等待 material screen change 和短稳定窗口，保留 `--no-wait` 与 120 秒 `--ready-timeout`，但 observation 不代表 composer ready。
- `launch` 的公开结果只保留 pane 信息和 observation，不回显 caller 已提供的 argv 或 preset 来源。
- runtime/config root 不可安全使用时返回稳定的领域错误，`doctor` 同步报告对应检查结果。
- preset save/update 改为显式输入 `agent_type`、可选 `pane_name` 和 argv；Agent registry 只保留两字符 `pane_prefix`。常规启动使用 preset，direct argv 作为临时路径。
- 版本改用标准 `with-agents --version`。

### 删除

- 删除 `request`、`reply`、`inbox`、`gc`、`create`、`restart` 和 `version` 子命令，以及 `scripts/launch-agent`。
- 删除 ticket、spool、event stream、notification callback、request route context 和专属 reply envelope。
- 删除 run ID target、launch record、`@with_agents_*` metadata 与 restart replay。
- 删除 observation credential、ownership/foreign gate、adapter capability gate 和 foreground-process inference。
- 删除 preset 的 `--from`、cwd、live-pane inference，以及 Agent registry 的 `executables` 字段。

### 升级

0.3 不读取 0.2 request runtime、observation credential 或 launch record，也不提供兼容 shim。升级前应先处理所有在途 request；确认不再需要后，可自行清理旧 runtime 数据。私有 `config.json` 中若存在 `executables`，必须删除。已符合 version 1 `agent_type`、`pane_name`、`argv` schema 的 0.2 preset 可继续读取；0.3 允许省略 `pane_name`。
