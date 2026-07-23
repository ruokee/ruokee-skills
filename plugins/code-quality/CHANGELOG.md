# Changelog

本文件记录 `code-quality` Skill 的主要变更。

版本号使用 `YYYY-MM-DD-rN` 格式，`rN` 表示同一日期内的第 N 次可追踪修订。

## 2026-07-01-r2

- 精简 `SKILL.md` 的进入条件，避免在入口处重复列举所有主题，把细粒度路由交给判断顺序表。
- 将路由表调整为 `Signal | Read First | Often Pair With` 三列结构，使 Agent 能直接从任务信号定位到首选叶子文档，并知道常见配合阅读的主题。
- 将详细输出格式从 `SKILL.md` 中移出，由不同 workflow 文档分别维护，避免入口文档与 workflow 重复。
- 补充输出语言约束：优先遵循系统、项目和用户指令，未明确指定时使用当前对话语言。

## 2026-07-01-r1

本次修订将初始版本重写为更接近正式 Skill 的结构。

- 将详细知识统一放入 `references/`，通过 `SKILL.md` 进行渐进式披露。
- 将原来的 review 模式文档调整为 `workflow/`，明确区分操作流程和概念知识。
- 建立 `design-principles/`、`design-patterns/`、`refactoring/`、`programming-paradigms/`、`agentic-coding/` 五个知识域。
- 扩充叶子文档，使其从简短知识卡片转向完整参考文档，覆盖概念、适用边界、误用形式和评估方式。
- 将 Agent / Skill 配置质量问题收敛到 `agentic-coding/config-smells.md`，避免与应用代码质量混在一起。

## 2026-06-30-r1

初始版本从「代码风格与编程范式」项目调研内容生成。

- 创建 `code-quality` Skill，用于通用代码质量、设计原则、设计模式、重构、编程范式和 Agent 配置质量判断。
- 提供顶层 `SKILL.md` 作为导航入口，并按主题拆分叶子文档。
- 建立设计原则、设计模式、重构、编程范式和 Agent 配置相关的初始文档集合。
- 提供快速审查和完整审查的早期 workflow 形态。
- 同时生成英文和中文两个语言变体，为后续安装时的语言选择打基础。
