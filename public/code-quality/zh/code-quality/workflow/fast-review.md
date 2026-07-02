# Fast Review — Code Quality

默认模式。开发后的快速高信号自检，或针对小 diff 的 review。优化目标是少量、把握高的发现，而不是覆盖率。倾向于对足够好的代码不做干预。

## 触发条件

- 未指定模式时默认使用。
- 日常开发自检。
- 小 diff、单文件或聚焦的 PR。

## 前提

- 只读。不要修改代码。
- 必须有明确目标：一个 diff、一个文件，或一组已命名的文件。如果范围是整个仓库或不清楚，就请用户收窄，或者按 full review 处理。

## 步骤

1. 确立项目事实。读最近的 `AGENTS.md`/`CLAUDE.md`，并扫一眼变更附近的代码，了解现有结构和约定。
2. 读取偏好，如果存在：先 `.agents/preferences/code-quality.md`，否则 `.agents/preferences/code-quality/index.md`。两者都不存在则继续。
3. 扫描 diff 或指定代码。优先使用 `git diff`、`git show`、`rg`、`nl`，而不是把全部内容都加载进来。
4. 用以下标准检查目标：
    - 错误的抽象——一个通用 helper、base class 或参数集合并不匹配真实 variation。
    - 过薄的 wrapper——一个函数或类只是重命名一个表达式，没有任何语义边界。
    - 知识重复——同一个规则、schema 或决策在两个地方重复出现（不是仅仅外观相似）。
    - 明显的 smell——长函数混合多个阶段、全局/散落状态、primitive obsession、shotgun surgery。
    - 模式误用——在还没有 variation point 时就套用了一个命名模式。
    - 没有测试就重构——在缺乏测试覆盖的代码上做行为可能改变的重组。
    - Agent 配置 smell——如果 review 的对象是 `AGENTS.md`/`SKILL.md`/prompt config：冲突、死规则、含糊指令、冗余。
5. 输出 0-5 个 findings，按信号强度从高到低排序。0 个 findings 也是有效且良好的结果。

## 输出格式

以 findings 开头，保持简洁。每个 finding 一块：

```text
- [severity, confidence] path:line Title
  Fact: observable evidence.
  Impact: why it matters — change cost, readability, correctness, testability.
  Recommendation: smallest sufficient change.
```

除非真的有信号，否则省略 Open Questions 和 Notes。不要为了凑满五条而填充内容。

## 停止规则

- 不要为了满足某个原则而编造 findings。干净的 diff 可以没有 findings。
- 不要为了 DRY 就建议抽象，除非能证明两个位置共享同一知识。
- 不要自动重构或重组；只报告，不动手。
- 不要自行升级到 full review——只有当 diff 明显需要更深入时才建议。
- 最多 5 条 findings；保留最有分量的部分。
- 跳过 formatter 或 linter 可以机械捕捉的问题。
- 不要把偏好当成普遍工程真理。
