# Task 设计文档

本目录是 Task 模块当前规范设计的长期权威，描述 Core、CLI、Agent contract、宿主适配器和 runtime Skill 共同遵守的边界与不变量。实现、测试或 runtime 文档改变这些语义时，应同步更新这里。

本目录从研究阶段的设计基线迁入后，独立维护当前规范。公开文档必须自包含，不依赖未随仓库发布的讨论记录或外部私有文档；历史材料可以单向引用本目录，本目录不建立反向引用。

## 文档状态

本目录表达已经决定的规范设计，可以领先于实现，但不得把计划态混入已交付行为：

- 各专题正文描述当前规范设计和已经实现的部分。
- 已决定但尚未实现或尚缺直接验证的内容集中记录在 [验证与范围](validation-and-scope.md#implementation-gaps)；相关专题只提供短链接。
- runtime Skill 和 references 只描述已经实现并获得代码、生成契约、测试或等价直接证据支持的行为。

## 文档地图

- [架构](architecture.md)：四层架构、进程边界、宿主集成、版本与分发。
- [Project 与存储](project-storage.md)：配置、project 发现、embedded/detached、目录和 Git 策略。
- [Task 模型](task-model.md)：身份、目录、`TASK.md`、关系、生命周期和 rename 不变量。
- [Agent 契约](agent-contracts.md)：五个高频操作、引用、actor、返回语义和调用入口。
- [Context 与 WAL](context-and-wal.md)：恢复、材料、read views、assignment、handoff 和活动记录。
- [一致性与失败边界](consistency-and-failures.md)：锁、原子写、并发、部分提交、竞态和诊断责任。
- [验证与范围](validation-and-scope.md)：纵向验收、测试层次、平台边界、implementation gaps 和明确延后项。

## 产品目标

Task 为 Codex、Claude Code、Pi 等 Agent 宿主提供一致的、项目绑定的持久任务能力。它保存一项已经决定推进的临时性努力的当前状态、相关材料和工作活动，使工作可以跨会话、跨 Agent 和跨上下文压缩继续。

Task 首先属于用户。Agent 负责协助创建、维护、恢复和推进，但 Task 的身份与事实不依赖某个模型、宿主、会话或 Agent runtime。

Task 是一个可安装的 package/plugin，不是单纯提示词 Skill，也不是试图统一所有 Agent 行为的通用 Harness。当前独立形态使用功能名 `task` 和默认 embedded root `.task/`；未来接入具名 Harness 时只增加外层命名空间，例如 `.foo/task/`。

## 核心原则

1. **模型与宿主无关**：持久化数据和 Core 契约不依赖具体模型或会话格式。
2. **确定性 Core**：发现、校验、关系、生命周期、锁和写入由同一个不调用 LLM 的 Core 执行。
3. **文件是事实来源**：Task 使用可读、可手工编辑的 Markdown/YAML；数据库不是权威状态。
4. **Task 轻，材料自由**：`TASK.md` 保存当前事实并指向材料，过程进入 WAL，详细内容使用普通文件。
5. **稳定身份，尽量稳定路径**：UUIDv7 是永久身份；状态变化和 archive 不移动目录。
6. **只强制高价值不变量**：Core 阻止身份不确定、managed fields 非法和关系/生命周期冲突，不穷尽所有人工异常。
7. **按需付出上下文成本**：`SKILL.md` 保留高频用法，完整 runtime 说明按专题放在 references 中。

## 明确边界

Task 不承担以下职责：

- 收集想法、TODO 或 backlog；
- 替代宿主 todo、plan 或临时执行清单；
- 持久化 current/active Task、session、assignee 或 lease；
- 提供 global Task root 或跨 project 结构化关系；
- 同步协议、分布式锁或跨设备冲突解决；
- 代码备份、自动 Git commit 或 branch 存在性保证；
- 数据库、daemon、全文检索服务、TUI/Web UI；
- 固定 handoff/checkpoint 模板；
- schema、storage mode 或 Git policy 的自动迁移。

## 权威与维护顺序

不同信息由不同表面负责：

1. Core 请求模型、实现和测试是机械行为的权威。
2. `package/contracts/task-tools.schema.json` 由请求模型生成，是宿主工具输入结构的发布表面。
3. `package/skills/task/references/` 是各 runtime 专题的完整自然语言说明。
4. `package/skills/task/SKILL.md` 是独立可用的高频投影，可以为零额外加载重复 reference 中的高频规则。
5. 本目录解释系统为什么这样分层、谁保证什么，以及变更时不能破坏哪些不变量。

行为变更时，先更新并验证 Core/契约，再更新对应完整 reference，最后判断高频投影是否也需要更新。自动检查负责生成契约、链接和文件可达性；自然语言等价性由评审与 forward-test 验证。

本目录不是安装说明或 runtime Agent 入口。宿主安装与开发命令见上级 [README](../README.md)，Agent 使用规则见 [Task Skill](../package/skills/task/SKILL.md)。
