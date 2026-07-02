# Skill 架构

## 概述

Python 专项工程：项目形态（project shape）、Python 版本策略、依赖管理、包布局、规范（样式、类型、测试、文档、自定义 lint）、语法选择、标准库机制和工具链。

## 结构

```
python-engineering/
├── SKILL.md
├── workflow/
│   ├── index.md
│   ├── fast-review.md
│   ├── full-review.md
│   └── analysis.md
└── references/
    ├── project/
    │   ├── index.md
    │   ├── structure.md
    │   ├── python-version.md
    │   └── dependency-management.md
    ├── spec/
    │   ├── index.md
    │   ├── style.md
    │   ├── type-hint.md
    │   ├── testing.md
    │   ├── docstrings-api-docs.md
    │   └── custom-lint.md
    ├── grammar/
    │   ├── index.md
    │   ├── match-case.md
    │   ├── context-manager.md
    │   ├── decorator.md
    │   └── exception-groups.md
    ├── stdlib/
    │   ├── index.md
    │   ├── common.md
    │   ├── functools.md
    │   ├── itertools.md
    │   └── contextlib.md
    └── tooling/
        ├── index.md
        ├── uv.md
        ├── ruff.md
        ├── ty.md
        ├── mypy.md
        ├── basedpyright.md
        ├── pytest.md
        ├── coverage.md
        ├── pre-commit.md
        └── flake8-plugin.md
```

## 领域职责

- **project**（项目）—— 项目形态分类、Python 版本策略、包结构（src-layout、flat-layout、packaged application、workspace）和依赖管理。
- **spec**（规范）—— 编码规范边界：样式、类型注解（语法和标注选择）、类型检查（工具和策略）、测试、文档和自定义 lint。
- **grammar**（语法）—— 影响设计的 Python 语法选择：结构化模式匹配（structural pattern matching）、上下文管理器、装饰器（语法、高阶函数、参数化装饰器、装饰器类）和异常组（exception groups）。
- **stdlib**（标准库）—— 值得作为设计选择了解的标准库机制，而非仅作为 API 参考。
- **tooling**（工具链）—— 工具职责、配置边界、命令风险以及与规范的关系。
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
