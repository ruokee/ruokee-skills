# python-engineering

## 用途

`python-engineering` 是 Python 专项工程 Skill，覆盖项目形态、Python 版本策略、依赖管理、包布局、类型注解、测试、自定义 lint、Python 语法、标准库机制、工具链和 Python 代码审查。它用于 Python 项目结构设计、规范设计、代码审查、工具链检查和 Python 工程实践分析。普通 Python 项目日常审查通常应与 `code-quality` 一起使用。

## 语言变体

`skills/python-engineering/` 是完整英文 base，也是 default 变体；`variants/zh/` 是相对 base 的稀疏中文 overlay。`docs/en/` 与 `docs/zh/` 保存两种语言的架构和设计维护文档，不进入安装结果。

```text
plugins/python-engineering/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── docs/{en,zh}/
├── skills/python-engineering/
├── variants/zh/
├── meta.toml
└── README.md
```

中文 overlay 覆盖英文 base 后，会物化出完整的中文 Skill。

## 安装

注册仓库 marketplace 后，default 英文版本使用宿主原生命令安装；Pi 直接安装本地 package 路径：

```bash
codex plugin add python-engineering@ruokee-skills
claude plugin install python-engineering@ruokee-skills --scope user
pi install /path/to/ruokee-skills/plugins/python-engineering
```

选择中文变体时，从仓库根目录运行：

```bash
uv run scripts/install.py setup python-engineering --scope user --variant zh
```
