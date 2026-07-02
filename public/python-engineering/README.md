# python-engineering

## 用途

`python-engineering` 是 Python 专项工程 Skill，覆盖项目形态、Python 版本策略、依赖管理、包布局、类型注解、测试、自定义 lint、Python 语法、标准库机制、工具链和 Python 代码审查。它用于 Python 项目结构设计、规范设计、代码审查、工具链检查和 Python 工程实践分析。普通 Python 项目日常审查通常应与 `code-quality` 一起使用。

## 语言变体

`python-engineering` 包含英文（en）变体与中文（zh）变体。

安装脚本后续应支持选择和切换变体；同一个目标目录下同一时间只安装一个 `python-engineering` 变体。

```text
├── en/
│   ├── python-engineering/
│   ├── architecture.md
│   └── design.md
└── zh/
    └── ...
```

- `<variant>/python-engineering/`：实际安装使用的 Skill 目录
- `architecture.md`：Skill 整体架构
- `design.md`：Skill 设计文档

当前 Skill 以中文变体为主，英文变体保持与中文变体同步。
