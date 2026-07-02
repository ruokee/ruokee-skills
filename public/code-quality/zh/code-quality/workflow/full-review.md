# Full Review — Code Quality

重度、系统性的 review。**仅限用户触发**——不要自行进入这个模式。它比 fast review 更慢、更彻底，采用分阶段阅读和自我验证。

## 触发条件

只有当用户明确要求 “full review”、“architecture review”、“design review” 或 “refactoring assessment” 时才进入。

## 步骤

### 1. 上下文采集

在广泛阅读之前，先写下：

- Review 目标——真正要评估的对象是什么（一个模块、一个子系统、一份重构计划、一个配置）。
- 必读内容——与目标核心相关的代码、配置或测试。
- 可选上下文——可能解释设计决策的邻近代码。
- 开放问题——哪些地方不确定、可能需要问用户。

### 2. 分阶段阅读

按问题领域逐步加载参考文档，而不是一次性全读。先读最近的 `AGENTS.md`/`CLAUDE.md`，再读偏好（`.agents/preferences/code-quality.md` 或 `.../code-quality/index.md`）。只有当某个具体信号指向它时，才拉取相应的原则、模式、重构或范式文档。读代码也要分阶段进行——先读目标，再根据某个发现需要再扩展范围。

### 3. 系统矩阵

围绕以下维度推进，并为每个 finding 记录证据：

- 变更方向和成本——下一步最可能的变化是什么，当前结构让它变得多贵。
- 原则张力——DRY vs KISS、抽象 vs 重复、灵活性 vs YAGNI。要写出取舍，不要教条式选边。
- 模式论证——对于每个命名模式，确认它所管理的 variation point 真实存在。
- smell 识别——长函数、重复知识、primitive obsession、feature envy、shotgun surgery、divergent change、thin wrappers。
- 范式匹配——imperative/OO/functional-core/data-oriented/state-machine 是否适合问题，还是在和问题对着干。
- 测试覆盖——行为是否已经足够被固定，能否安全重构。
- Agent 配置——如相关，评估 `AGENTS.md`/`SKILL.md`/workflow config 是否存在冲突、死规则或不清晰。

### 4. 自我验证高严重度发现

对每个高严重度 finding，重新核对证据，说明置信度，并主动考虑误报的可能：这种结构是否是刻意设计，或者是某个尚未看到的 reason-to-change 所驱动。如果站不住脚，就降级或删除 finding。

### 5. 确认停止

在建议或执行任何以下事项前先停下并询问：跨文件重构、架构迁移或批量变更。先展示计划及其成本，让用户决定。

## 输出格式

```text
Findings

- [severity, confidence] path:line Title
  Fact: observable evidence.
  Impact: change cost, readability, correctness, testability.
  Judgment: principle, pattern, smell, paradigm mismatch, or config smell.
  Evidence: support, counter-evidence, and remaining uncertainty.
  Recommendation: smallest sufficient change.
  Verification: command/check, or why none is needed.

Open Questions
- Items needing user or project confirmation.

Notes
- Downgraded, deliberate, or tool-handled items, with why.
```

按类别分组 findings。要明确写出哪些被降级了，以及为什么。

## 停止规则

- 没有明确要求时不要修改代码。
- 对跨文件重构、迁移和批量变更必须先确认停止。
- 不要为了满足原则而硬找问题，也不要仅凭相似就抽象。
- 不要把偏好当作普遍工程真理。
- 每条 finding 都要把 fact、judgment、preference 和 recommendation 区分清楚。
