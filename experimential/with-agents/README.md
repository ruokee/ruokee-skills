# with-agents

## 用途

`with-agents` 教会当前 Agent 如何发现、启动、读取和操作外部 Agent CLI，适用于用户明确指定外部 CLI、已有 Agent pane、tmux 交互或需要持久保留的外部 Agent 工作。

它将外部 Agent CLI 作为普通交互式终端程序，只使用 tmux 作为中间层。当前 harness 的原生 subagent 能完成普通委派时优先使用原生能力；仅当用户明确指定外部 CLI、tmux 或本 Skill 时才使用本模块。

## 树结构

```text
experimential/with-agents/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── meta.toml                  # 安装器 meta-v2 入口
├── skills/with-agents/        # 完整英文 base，也是唯一规范 Skill 源
│   ├── agents/openai.yaml
│   ├── references/           # CLI、preset、消息、状态、pane、adapter 与 tmux 恢复
│   ├── scripts/
│   │   ├── launch-agent      # with-agents launch 的薄 shortcut
│   │   └── with-agents       # 统一控制器（正常操作入口）
│   └── SKILL.md
├── variants/zh/               # 相对 Skill 根的稀疏中文 overlay
│   ├── agents/openai.yaml
│   ├── references/
│   └── SKILL.md
├── tests/
│   ├── fixtures/
│   │   └── mock_agent.py
│   └── test_with_agents.py
└── README.md
```

## 语言变体

- `skills/with-agents/` 是完整英文 base，所有命令行行为和语义以它为准。
- `variants/zh/` 只保存可翻译文件；安装器将它覆盖到英文 base 上，物化完整中文 Skill。
- `scripts/with-agents` 和 `scripts/launch-agent` 只在英文 base 中保留一份，中文变体直接继承，因此两种物化结果的可执行文件逐字节一致。
- 私有 preset 位于用户配置目录 `${XDG_CONFIG_HOME:-~/.config}/with-agents/presets/` 中，**不在本仓库内**。
- Agent 类型注册表位于 `${XDG_CONFIG_HOME:-~/.config}/with-agents/config.json`；它只影响需要 registry 的命名与 generic callback 能力，不替代代码内置的 Codex/Pi capability adapter。

## 安装路径

Marketplace plugin 与仓库安装器是两条互斥的分发路径；同一宿主不要同时安装两份 `with-agents`。

Codex 和 Claude marketplace 只暴露默认英文 Skill：

```bash
# 在 Codex/Claude 中先注册本仓库 marketplace，再选择 with-agents 安装。
codex plugin marketplace add /path/to/ruokee-skills
codex plugin add with-agents@ruokee-skills

claude plugin marketplace add /path/to/ruokee-skills
claude plugin install with-agents@ruokee-skills
```

中文或显式选择英文时，从仓库根目录使用安装器：

```bash
uv run --script scripts/install.py install with-agents --variant en --global --target codex
uv run --script scripts/install.py install with-agents --variant zh --global --target codex
```

将 `--target codex` 改为 `--target claude` 可安装到 Claude 的全局 Skill 目录。Plugin 安装使用宿主 cache，不是源码 live mount；源码更新后需要按宿主的重装流程刷新。

## 操作方式

所有正常操作通过统一的 `scripts/with-agents` 控制器完成。`scripts/launch-agent` 是 `with-agents launch` 的薄 shortcut，接受相同选项。

`send` 只提交消息，不创建 ticket；`request` 创建 v2 异步 event stream，允许 child 追加 `progress`、`question`，并以 `done`、`blocked` 或 `failed` 封口。request 提交后 caller 应释放 turn，以 spool 中按 `seq` 排序的事件为权威结果，不用 `read`、`wait` 或 `inbox` 建立轮询循环。

控制器统一管理 pane 生命周期、观察凭据、event 持久化和尽力 callback；不使用过时的 `tmux-bridge`、`tmux-setup` 或拷贝自 smux 的脚本。原生 tmux 仅作为故障恢复入口——仅在控制器不可用、`doctor` 报告后端问题或需要手工恢复部分输入时，才参考 `references/tmux-recovery.md`。

## 撰写与设计边界

以下内容约束本 Skill 的撰写和维护范围，不写入可安装的 `SKILL.md`：

- 不预设 Agent 的固定角色、层级或任务类型；这些由当次请求决定。
- 不要求安装额外 broker、daemon 或 MCP server，也不定义通用的结果协议或跨任务编排状态。
- 不覆盖当前 harness、用户或目标 CLI 已有的配置和权限。
- 不把 tmux session 或 pane 描述为 sandbox；tmux 只是终端中间层。
- Agent 仍在执行、等待或自动重试时持续保留其 pane，不以固定等待时长或重试次数作为退出条件。
- 创建的 pane 保留到外层任务或 goal 完全结束；预先存在的用户 pane 不自动关闭。

## 运行测试

```bash
python -B -m unittest discover -s experimential/with-agents/tests
```

测试验证 meta-v2 物化、preset 与 Agent config、v1/v2 request 共存、event 顺序与资源预算、pane 身份变更、callback adapter 和共享脚本等核心合同。
