# Changelog

本文件记录 `python-engineering` Workspace 中可安装 Skill 产物的主要变更。

版本号使用 `YYYY-MM-DD-rN` 格式，`rN` 表示同一日期内的第 N 次可追踪修订。

## 2026-07-01-r2

- 精简 `SKILL.md` 的进入条件，避免在入口处重复列举所有 Python 工程主题，把细粒度路由交给判断顺序表。
- 将路由表调整为 `Signal | Read First | Often Pair With` 三列结构，使 Agent 能直接从任务信号定位到首选叶子文档，并知道常见配合阅读的主题。
- 将详细输出格式从 `SKILL.md` 中移出，由不同 workflow 文档分别维护，避免入口文档与 workflow 重复。
- 补充输出语言约束：优先遵循系统、项目和用户指令，未明确指定时使用当前对话语言。
- 细化 `references/spec/type-hint.md` 中的类型检查分层，区分静态类型检查和运行时类型检查。
- 在静态类型检查部分按 mypy、pyright、basedpyright、ty 的顺序介绍工具定位，并说明 ty 作为新工具需要注意行为变化。
- 在运行时类型检查部分以 Pydantic、msgspec 为代表，说明边界校验机制，不展开数据模型细节。

## 2026-07-01-r1

本次修订将初始版本重写为更接近正式 Skill 的结构。

- 将详细知识统一放入 `references/`，通过 `SKILL.md` 进行渐进式披露。
- 将原来的 review 模式文档调整为 `workflow/`，明确区分操作流程和概念知识。
- 将项目结构主题收敛到 `references/project/structure.md`，统一覆盖 src layout、flat layout、packaged application 和 workspace。
- 将类型别名、类型参数和类型检查策略归入 `references/spec/type-hint.md`，避免把同一类类型设计问题拆散。
- 新增 `references/grammar/decorator.md`，统一说明装饰器语法、高阶函数、带参装饰器和装饰器类。
- 将 `pre-commit` 作为本地工具链机制记录，不再把 CI 作为默认前提。
- 扩充叶子文档，使其从简短知识卡片转向完整参考文档，覆盖概念、适用边界、误用形式和评估方式。

## 2026-06-30-r1

初始版本从「代码风格与编程范式」项目调研内容生成。

- 创建 `python-engineering` Skill，用于 Python 项目形态、版本策略、依赖管理、包布局、类型、测试、文档、自定义 lint、语法、标准库和工具链判断。
- 提供顶层 `SKILL.md` 作为导航入口，并按主题拆分叶子文档。
- 建立 project、spec、grammar、stdlib、tooling 和 review 相关的初始文档集合。
- 提供快速审查、完整审查、上下文读取和只读调查的早期 workflow 形态。
- 同时生成英文和中文两个语言变体，为后续安装时的语言选择打基础。
