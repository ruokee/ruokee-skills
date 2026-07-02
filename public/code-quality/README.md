# code-quality

## 用途

`code-quality` 是通用代码质量 Skill，覆盖设计原则、设计模式、重构、编程范式、代码坏味道、状态机、资源生命周期、抽象质量，以及 Agent / Skill 配置坏味道。它用于代码审查、架构审查、重构评估、设计讨论和 Agent 配置质量检查。

## 语言变体

`code-quality` 包含英文（en）变体与中文（zh）变体。

安装脚本后续应支持选择和切换变体；同一个目标目录下同一时间只安装一个 `code-quality` 变体。

```text
├── en/
│   ├── code-quality/
│   ├── architecture.md
│   └── design.md
└── zh/
    └── ...
```

- `<variant>/code-quality/`：实际安装使用的 Skill 目录
- `architecture.md`：Skill 整体架构
- `design.md`：Skill 设计文档

当前 Skill 以英文变体为主，中文变体保持与英文变体同步。
