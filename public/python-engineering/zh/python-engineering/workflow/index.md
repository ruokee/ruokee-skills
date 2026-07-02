# 工作流

此 Skill 运行在三种模式之一。先阅读对应文档，然后执行。

|模式|何时使用|文档|
|-|-|-|
|Fast review|默认。开发后的日常自检、小 diff、单文件或 PR review。|[fast-review.md](./fast-review.md)|
|Full review|只有当用户明确要求“full review”、“complete review”、“systematic review”或“architecture review”时。|[full-review.md](./full-review.md)|
|Analysis|讨论、设计比较、机制解释、重构规划、项目结构设计。没有 diff 需要评分。|[analysis.md](./analysis.md)|

默认使用 fast review。不要自行升级到 full review - 它更重，必须由用户触发。只要用户是在问“该怎么做”而不是“哪里错了”，就切换到 analysis。

这三种模式都默认只读。只有在用户要求修复时才修改代码，并且在任何不安全、批量或跨文件变更之前先停下来征求确认。
