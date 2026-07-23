# frontend-design

Anthropic 官方 `frontend-design` Skill。

## 来源

- 上游仓库：https://github.com/anthropics/skills
- 上游路径：`skills/frontend-design`
- 引入 ref：`main`
- 引入 commit：`9d2f1ae187231d8199c64b5b762e1bdf2244733d`
- 引入日期：2026-07-02
- 许可证：Apache-2.0，完整条款见 `skills/frontend-design/LICENSE.txt`

## 选用原因

这个 Skill 适合在构建或重塑前端界面时，约束 Agent 不要产出模板化、缺少视觉判断的默认设计。它强调从具体主题出发，先建立配色、字体、布局和标志性设计元素，再进入实现与自我审查。

## 本地结构

```text
plugins/frontend-design/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── skills/frontend-design/
│   ├── LICENSE.txt
│   └── SKILL.md
├── meta.toml
└── README.md
```

当前保留原始 Skill 内容，未做本地改写。锁定上游与托管路径记录在 `meta.toml` 的 `[upstream]` 中。

## 安装

注册仓库 marketplace 后，Codex 和 Claude Code 使用宿主原生命令安装；Pi 直接安装本地 package 路径：

```bash
codex plugin add frontend-design@ruokee-skills
claude plugin install frontend-design@ruokee-skills --scope user
pi install /path/to/ruokee-skills/plugins/frontend-design
```
