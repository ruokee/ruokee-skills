# Skill 架构

## 概述

语言无关的软件质量：设计原则、设计模式、重构（Fowler 风格）、编程范式，以及智能体配置坏味（agent configuration smells）。

## 结构

```
code-quality/
├── SKILL.md
├── workflow/
│   ├── index.md
│   ├── fast-review.md
│   ├── full-review.md
│   └── analysis.md
└── references/
    ├── design-principles/
    │   ├── index.md
    │   ├── dry.md
    │   ├── rule-of-three.md
    │   ├── kiss.md
    │   ├── yagni.md
    │   ├── solid.md
    │   ├── grasp.md
    │   ├── law-of-demeter.md
    │   ├── tell-dont-ask.md
    │   ├── composition-over-inheritance.md
    │   ├── dependency-inversion.md
    │   ├── tdd.md
    │   ├── ddd.md
    │   └── deep-modules.md
    ├── design-patterns/
    │   ├── index.md
    │   ├── factory.md
    │   ├── abstract-factory.md
    │   ├── builder.md
    │   ├── strategy.md
    │   ├── observer.md
    │   ├── adapter.md
    │   ├── decorator.md
    │   ├── facade.md
    │   ├── command.md
    │   ├── state.md
    │   ├── visitor.md
    │   ├── repository.md
    │   └── unit-of-work.md
    ├── refactoring/
    │   ├── index.md
    │   ├── fowler-refactoring.md
    │   ├── code-smells.md
    │   ├── safe-refactoring.md
    │   ├── long-function.md
    │   ├── duplicated-code.md
    │   ├── primitive-obsession.md
    │   ├── feature-envy.md
    │   ├── shotgun-surgery.md
    │   ├── divergent-change.md
    │   ├── thin-wrapper-function.md
    │   ├── extract-function.md
    │   ├── inline-function.md
    │   └── move-function.md
    ├── programming-paradigms/
    │   ├── index.md
    │   ├── imperative.md
    │   ├── declarative.md
    │   ├── object-oriented.md
    │   ├── functional-core.md
    │   ├── data-oriented.md
    │   ├── event-driven.md
    │   ├── state-machine.md
    │   ├── resource-lifecycle.md
    │   └── async-concurrency.md
    └── agentic-coding/
        ├── index.md
        └── config-smells.md
```

## 领域职责

- **design-principles**（设计原则）—— 判断框架。每个原则文档解释该原则、其假设、适用时机、与其他原则冲突时如何处理，以及如何据此评估代码。
- **design-patterns**（设计模式）—— 具体命名的模式。每个文档解释模式解决的问题、典型实现、使用时机、不适用场景，以及如何识别误用。
- **refactoring**（重构）—— Fowler 风格的保持行为不变的改进方法。代码坏味（code smells）、命名重构手法，以及安全重构的规范。
- **programming-paradigms**（编程范式）—— 问题形态到范式的匹配。每个范式文档解释其含义、假设、适用场景，以及如何评估代码是否恰当使用了该范式。
- **agentic-coding**（智能体配置）—— 智能体规则、Skill、提示词和工作流文档中的配置坏味。与代码质量分开，因为被审查的"代码"是配置而非应用逻辑。
- **workflow**（工作流）—— 操作模式。快速审查（fast review）用于日常自检。完整审查（full review）用于显式要求的全面评估。分析（analysis）用于设计讨论和探索。

## SKILL.md 结构

`SKILL.md` 文件按以下顺序组织章节：

1. **进入条件（Entry Conditions）** —— 何时激活此 Skill。
2. **模式选择（Mode Selection）** —— 默认快速审查；完整审查需显式请求；分析模式用于讨论和设计。
3. **判断顺序（Judgment Order）** —— 信号到叶子节点的路由表，以及在阅读叶子节点前如何分析问题。
4. **偏好（Preferences）** —— 发现机制和使用规则。
5. **输出约定（Output Contract）** —— 发现结果结构、事实/判断/偏好的分离。
6. **停止规则（Stop Rules）** —— Skill 不得自动执行的操作。

对于只读请求（仓库概览、"请勿修改"、外部代码分析），`SKILL.md` 直接在文件中说明约束，而非委托给单独文档。
