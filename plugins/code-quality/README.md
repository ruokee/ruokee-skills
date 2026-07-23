# code-quality

## 用途

`code-quality` 是通用代码质量 Skill，覆盖设计原则、设计模式、重构、编程范式、代码坏味道、状态机、资源生命周期、抽象质量，以及 Agent / Skill 配置坏味道。它用于代码审查、架构审查、重构评估、设计讨论和 Agent 配置质量检查。

## 语言变体

`skills/code-quality/` 是完整英文 base，也是 default 变体；`variants/zh/` 是相对 base 的稀疏中文 overlay。`docs/en/` 与 `docs/zh/` 保存两种语言的架构和设计维护文档，不进入安装结果。

```text
plugins/code-quality/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── docs/{en,zh}/
├── skills/code-quality/
├── variants/zh/
├── meta.toml
└── README.md
```

中文 overlay 覆盖英文 base 后，会物化出完整的中文 Skill。

## 安装

注册仓库 marketplace 后，default 英文版本使用宿主原生命令安装；Pi 直接安装本地 package 路径：

```bash
codex plugin add code-quality@ruokee-skills
claude plugin install code-quality@ruokee-skills --scope user
pi install /path/to/ruokee-skills/plugins/code-quality
```

选择中文变体时，从仓库根目录运行：

```bash
uv run scripts/install.py setup code-quality --scope user --variant zh
```
