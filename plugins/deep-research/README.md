# deep-research

## 用途

`deep-research` 用于结构化、证据优先的深度调研。

它的核心目标是让 Agent 在写结论前先充分探索、收集和交叉验证来源，并在输出中区分事实、推断、判断、建议和待确认问题。

## 本地结构

```text
plugins/deep-research/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── skills/deep-research/
├── meta.toml
└── README.md
```

`skills/deep-research/` 是实际可安装的 default Skill。`meta.toml` 将该插件标记为实验性，但不影响本地 marketplace 可见性。

## 安装

注册仓库 marketplace 后，Codex 和 Claude Code 使用宿主原生命令安装；Pi 直接安装本地 package 路径：

```bash
codex plugin add deep-research@ruokee-skills
claude plugin install deep-research@ruokee-skills --scope user
pi install /path/to/ruokee-skills/plugins/deep-research
```
