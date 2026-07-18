# with-agents

## 用途

`with-agents` 用于在用户明确指定外部 Agent CLI、已有 Agent pane、tmux 交互或本 Skill 时，教会当前 Agent 如何发现、启动、读取和操作其他 Agent CLI。

它把 Agent CLI 当作普通交互式终端程序，只使用 tmux 作为中间层。当前 harness 已提供原生 subagents 时，普通委派优先使用原生能力；用户明确指定外部 CLI、tmux 或本 Skill 时例外。

## 语言变体

```text
experimential/with-agents/
├── en/
│   └── with-agents/
│       ├── agents/
│       │   └── openai.yaml
│       ├── references/
│       │   ├── tmux-bridge.md
│       │   ├── tmux-setup.md
│       │   └── tmux.md
│       ├── scripts/
│       │   └── tmux-bridge
│       └── SKILL.md
├── zh/
│   └── with-agents/
│       ├── agents/
│       │   └── openai.yaml
│       ├── references/
│       │   ├── tmux-bridge.md
│       │   ├── tmux-setup.md
│       │   └── tmux.md
│       ├── scripts/
│       │   └── tmux-bridge
│       └── SKILL.md
└── README.md
```

`en/with-agents/` 是英文源版本；`zh/with-agents/` 从英文版本翻译并保持行为一致。安装时选择其中一个同名 Skill 变体。

## 撰写与设计边界

以下内容约束本 Skill 的撰写和维护范围，不作为运行时操作说明写入可安装的 `SKILL.md`：

- 不预设 Agent 的固定角色、层级或任务类型；这些由当次请求决定。
- 不要求安装额外 broker、daemon 或 MCP server，也不增加数据库、消息队列、结果 schema 或持久化状态。
- 不为了使用本 Skill 引入 worktree 或固定 Agent 拓扑。
- 不在 Skill 中介绍、比较或限制具体 Agent CLI。
- 不覆盖当前 harness、用户或目标 CLI 已有的配置和权限。
- 不把 tmux session 或 pane 描述为 sandbox；tmux 只是终端中间层。

## 运行时原则

- Agent 仍在执行、等待或自动重试时持续保留其 pane，不以固定等待时长或重试次数作为退出条件。
- 原生 tmux 是默认控制接口；在用户请求、现有流程已使用或读取保护与标签确有价值时，可使用已安装命令或 Skill 附带的 `tmux-bridge`。两个接口都保持读取、字面输入、确认和单独发送 Enter 的原子交互顺序。
- 两个语言变体均附带可直接调用的 `scripts/tmux-bridge`；将其安装到 `PATH`、覆盖已有命令或修改 shell 配置前，必须分别取得用户的明确授权。
- 创建新 pane 前先检查现有 pane；与当前对话有关、用户明确指定或已确认空闲时，优先尝试复用。需要全新上下文时，使用目标 CLI 已确认的清空或重置机制，不把清空终端画面当作清空对话。
- 调用方已在 tmux 中时，新建 window 或 pane 默认放在当前 session，便于用户通过鼠标或普通 window/pane 切换直接访问；用户明确指定其他 session 或 pane 时，以指定目标为准。调用方不在 tmux 中时，优先复用合适的现有 session，确无合适目标再新建 session。
- 当前交互创建的 pane 保留到外层用户任务或 goal 完全结束，并可用于后续对话、修改和审查；任务结束后再按需清理。预先存在的用户 pane 不自动关闭。

## 参考项目

交互流程主要参考 [ShawnPana/smux](https://github.com/ShawnPana/smux)，尤其是 pane 发现、发送前读取、字面文本与 Enter 分离、以及在消息中携带回复 pane 的做法。审阅基准为 [`70a6899`](https://github.com/ShawnPana/smux/tree/70a6899bdec5d3d3b51d9b927c0c0db0e22bb73f)，smux 使用 MIT License。本 Skill 不依赖 smux 安装器或个人 tmux 配置。

`references/tmux-bridge.md` 基于 smux 同 revision 的 [原始参考文档](https://github.com/ShawnPana/smux/blob/70a6899bdec5d3d3b51d9b927c0c0db0e22bb73f/skills/smux/references/tmux-bridge.md) 引入并适配，保留原作者和完整 MIT License。附带的 `scripts/tmux-bridge` 来自同 revision 的[上游脚本](https://github.com/ShawnPana/smux/blob/70a6899bdec5d3d3b51d9b927c0c0db0e22bb73f/scripts/tmux-bridge)，本地调整了消息提示、read guard 的 pane 身份校验、行数参数校验和空标签统计，并在脚本中保留完整 MIT License。参考文档还将上游的直接回复假设纳入本 Skill 的持久等待与 pane 生命周期规则；`references/tmux.md` 则独立整理原生 tmux 的完整操作流程。

其他用于确认设计边界的项目：

- [Claude Squad](https://github.com/smtg-ai/claude-squad)：将任意 Agent 视为 tmux 中可启动的终端命令。
- [CLI Agent Orchestrator](https://github.com/awslabs/cli-agent-orchestrator)：保留原生 CLI/PTY 与人工 attach，但其 MCP 和编排层不进入本 Skill。
- [claude-tmux-orchestration](https://github.com/primeline-ai/claude-tmux-orchestration)：补充多行文本的 buffer/paste 交互方式。
- [Agent Deck](https://github.com/asheshgoplani/agent-deck) 与 [dmux](https://github.com/standardagents/dmux)：用于对比通用 CLI 承载与完整编排产品的边界。
