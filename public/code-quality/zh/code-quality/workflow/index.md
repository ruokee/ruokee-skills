# 工作流

这个 Skill 有三种模式。先读匹配的文档，再行动。

|模式|何时使用|文档|
|-|-|-|
|快速 review|默认。开发后的日常自检、小 diff、单文件或 PR review。|[fast-review.md](./fast-review.md)|
|完整 review|只有当用户明确要求 “full review”、“architecture review”、“systematic review” 或 “refactoring assessment” 时才使用。|[full-review.md](./full-review.md)|
|分析|设计讨论、模式/范式比较、重构规划、结构设计。没有 diff 可判。|[analysis.md](./analysis.md)|

默认使用快速 review。不要自行升级到 full review——它更重，而且必须由用户触发。只要用户是在问“怎么做”而不是“哪里错了”，就切换到分析模式。

三种模式都默认只读。只有在用户要求修复时才修改代码，并且在任何不安全、批量或跨文件变更前停下来确认。
