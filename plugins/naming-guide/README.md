# naming-guide

## 用途

`naming-guide` 用于产品、项目、repo、package、module、CLI、API、数据结构、能力边界和领域概念的命名探索。

它的核心目标是让 Agent 先理解命名对象和使用表面，再发散候选路线，最后用中立比较和追加式命名记录辅助用户决策。

## 本地结构

```text
plugins/naming-guide/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── skills/naming-guide/
├── meta.toml
└── README.md
```

`skills/naming-guide/` 是实际可安装的 default Skill。

## 状态

这个 Skill 在实际使用中已经有一定效果，但交互和结果质量还不够稳定，因此 `meta.toml` 仍将它标记为实验性。该属性不影响本地 marketplace 可见性。

## 安装

注册仓库 marketplace 后，Codex 和 Claude Code 使用宿主原生命令安装；Pi 直接安装本地 package 路径：

```bash
codex plugin add naming-guide@ruokee-skills
claude plugin install naming-guide@ruokee-skills --scope user
pi install /path/to/ruokee-skills/plugins/naming-guide
```
