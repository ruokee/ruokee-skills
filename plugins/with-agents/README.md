# with-agents

## 用途

`with-agents` 为外部 Agent CLI 提供一层 tmux 交互包装：发现或启动 pane、读取画面、发送带回复地址的消息，以及管理 pane 生命周期。用户明确指定 with-agents、某个外部 CLI、tmux 或现有 pane，或者当前 harness 缺少所需模型时使用；普通委派优先使用 harness 原生 subagent。

## 树结构

```text
plugins/with-agents/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── CHANGELOG.md
├── meta.toml                  # 安装器 meta-v2 入口
├── skills/with-agents/        # 完整英文 base，也是规范 Skill 源
│   ├── agents/openai.yaml
│   ├── references/            # CLI、消息、状态、pane、preset 与 tmux 恢复
│   ├── scripts/
│   │   └── with-agents        # 标准库单文件 controller
│   └── SKILL.md
├── variants/zh/               # 相对 Skill 根的稀疏中文 overlay
│   ├── agents/openai.yaml
│   ├── references/
│   └── SKILL.md
├── tests/
│   ├── fixtures/mock_agent.py
│   └── test_with_agents.py
└── README.md
```

## 语言变体

- `skills/with-agents/` 是完整英文 base，命令行合同以它为准。
- `variants/zh/` 只保存可翻译文件；安装器将 overlay 覆盖到英文 base，物化完整中文 Skill。
- controller 只保留一份，中文变体直接继承，因此两种物化结果的可执行文件逐字节一致。
- 私有 preset 位于 `${XDG_CONFIG_HOME:-~/.config}/with-agents/presets/`，Agent registry 位于同级 `config.json`。仓库不保存用户模型、凭据或私有 argv。

## 安装

Codex 和 Claude marketplace 暴露英文 Skill，Pi 安装本地 package：

```bash
codex plugin marketplace add /path/to/ruokee-skills
codex plugin add with-agents@ruokee-skills

claude plugin marketplace add /path/to/ruokee-skills --scope user
claude plugin install with-agents@ruokee-skills --scope user

pi install /path/to/ruokee-skills/plugins/with-agents
```

选择中文变体时，从仓库根运行：

```bash
uv run scripts/install.py setup with-agents --scope user --variant zh
```

宿主会把插件复制到 cache，不会 live mount 源码。宿主更新后若恢复英文 default，运行 `uv run scripts/install.py update with-agents --scope user` 重放已记录的中文 overlay。

## 0.3 操作合同

公共命令只有 `read`、`send`、`list`、`launch`、`wait`、`key`、`close`、`preset`、`doctor` 和 `route`；版本通过 `with-agents --version` 查看。

pane 命令接受四种 TARGET：`%pane-id`、实时 `window_name`、`session:window.pane` 或 with-agents route。public `name` 始终来自当前 tmux window；split panes 共享 name，因此 pane ID 才是精确定位字段。唯一 canonical route 始终包含实时 name、decimal pane ID 和 canonical absolute socket，例如 `with-agents:tmux?name=cx-wa&pane_id=76&socket=/tmp/tmux-1000/default`。所有公共 pane 结果和默认消息 header 都返回该完整 route；`list --detail` 只增加诊断字段。带 with-agents 前缀但缺少 socket 的输入无效，裸 name、`%pane-id` 和 `session:window.pane` 仍是当前 server 内的 TARGET 便捷写法。

默认 `send` 从 `$TMUX` 和 `$TMUX_PANE` 取得发送方地址，并提交一条完整输入：

```text
[with-agents:tmux?name=cx-wa&pane_id=76] MESSAGE
```

`--request` 在 sender route 中加入 `reply=required` 和 8 位 correlation ID；`--correlation-id` 可在普通回信中复用已有 ID；`--params` 接受严格的 `{string: string}` JSON object。接收方先读取 header route，再用普通 `send ROUTE --correlation-id ID -- MESSAGE` 回信。route 中已有的 params 只供接收方阅读，不参与寻址，也不会传播到下一条消息。发送 CLI 自身的 `/new`、`/clear`、授权回答或明确的 shell 输入时使用 `--no-header`。

`send` 在 pane lock 内执行一次 `paste-buffer -p` 和一次 Enter，同一 pane 的 controller 操作因此串行。目标是否把带换行的正文解释成一个 composer value 取决于其 bracketed-paste 支持；controller 不把一次 paste 扩大为目标级“一次提交”保证。lock 释放后 controller 做一次有界画面观察；普通文本输出就是动作后的 snapshot，JSON 只补充 tmux 动作状态和实际构造的消息 metadata，不声称目标 Agent 已接受或开始处理。

`launch --preset PRESET` 是常规启动路径。临时 direct argv 在新 window 中使用 `launch --name FULL -- ARGV...`，拆分现有 window 时使用 `launch --split TARGET -- ARGV...`。launch 默认观察画面相对 baseline 的实质变化：画面短暂稳定时立即返回，持续变化到 `--ready-timeout` 时返回最新 snapshot 和 `stable=false`，始终没有实质变化才报 `launch_timeout`；`--no-wait` 才立即返回，默认 timeout 为 120 秒。将稳定画面视为启动观察结果；它可能是 splash、授权或登录提示。发送任务前确认 composer ready。

preset 只保存显式提供的 `agent_type`、可选 `pane_name` 和 argv，不保存 cwd，也不从 pane 或进程推断。缺省 pane name 按 Agent 的两字符 prefix 生成一次 `<prefix>-NNNN`。Agent registry 只配置 `pane_prefix`。

pane 是实时状态。Agent 在任何变更前先 `list`/`read` 确认目标；controller 会在 pane lock 内再次复核地址，但不保存观察凭据，不检查 idle/busy，也不建立 ownership 或 foreground-process 权限层。唯一权限式 hard stop 是拒绝变更 caller 自己的 pane。

## 从 0.2 升级

0.3 不读取 0.2 的 request runtime、observation credential 或 launch record，也不提供兼容 shim。升级前先处理在途 request；确认不再需要后，可自行清理旧 runtime 中的 `requests/`、`observations/`、notification/event 数据和 pane records。

以下入口与合同已删除：

- `request`、`reply`、`inbox`、`gc`、`create`、`restart` 和 `version` 子命令；
- `scripts/launch-agent`；
- ticket、spool、event stream、notification callback 和 request route context；
- run ID target、launch record、`@with_agents_*` metadata；
- observation credential、owned/foreign gate、adapter capability gate；
- preset 的 `--from`、cwd 与 executable inference。

已有 `${XDG_CONFIG_HOME:-~/.config}/with-agents/config.json` 若包含 `executables`，需删除该字段；每个 Agent 定义现在只接受 `pane_prefix`。已符合 version 1 `agent_type`、`pane_name`、`argv` schema 的 0.2 preset 可继续读取；`pane_name` 在 0.3 变为可选，其他额外字段需删除。

## 设计边界

- 不预设 Agent 的角色、层级或任务类型。
- 不安装 broker、daemon 或 MCP server，也不覆盖目标 CLI 的配置和权限。
- tmux 不是 sandbox。显式向 shell pane 发送文字并按 Enter 可能执行命令。
- Agent 仍在执行、等待或自动重试时保留 pane；外层任务和审查结束后再关闭本次创建的 pane。

## 测试

```bash
python -B -m unittest plugins.with-agents.tests.test_with_agents
```

测试覆盖最终 CLI surface、canonical route 回喂、逗号 socket 与 self-target、tmux vis window name、跨 socket reply、bracketed-paste 边界、原子输入队列、wait、launch observation 与 compact result、显式 preset、private root 错误和中英文 overlay 结构。
