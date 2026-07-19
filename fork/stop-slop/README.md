# stop-slop

基于 Hardik Pandya `stop-slop` 修改的个人 fork，用于清理英文和中文文本中常见的 AI 写作模式。

## 来源

- 引入仓库：https://github.com/amosblomqvist/pi-config
- 上游路径：`skills/stop-slop`
- 引入 ref：`main`
- 引入 commit：`575a0a5261ada93cf09189ebd59a508040f866f9`
- 原始项目：https://github.com/hardikpandya/stop-slop
- 原作者：Hardik Pandya
- 引入日期：2026-07-19
- 许可证：MIT，完整条款见 `stop-slop/LICENSE.txt`

Skill 内容取自 `pi-config` 的上述 commit。该仓库声明内容来自 Hardik Pandya，但没有提交 README 中列出的 `LICENSE` 文件；本地的 `LICENSE.txt` 取自原始项目 commit `8da1f030185bdfe8471220585162991eaeb970e9`。

## 选用原因

这个 Skill 把常见的 AI 写作痕迹拆成短语、结构、节奏和具体性问题，适合在草稿完成后做一轮有针对性的清理。规则短，reference 分工明确，也不依赖脚本或外部服务。

## Fork 内容

- 保留上游 `SKILL.md`、`references/examples.md`、`references/phrases.md` 和 `references/structures.md` 的内容与结构。
- 新增 `references/chinese.md`，只补充中文高频 AI 表达、互联网黑话和必要的中文语法例外。
- 在 `SKILL.md` 的 Examples 之后增加一条中文 reference 入口，不改动 frontmatter、Core Rules 和 Quick Checks。
- 不增加多语言目录变体。

## 本地结构

```text
fork/stop-slop/
├── stop-slop/
│   ├── references/
│   │   ├── chinese.md
│   │   ├── examples.md
│   │   ├── phrases.md
│   │   └── structures.md
│   ├── LICENSE.txt
│   └── SKILL.md
├── README.md
└── upstream.toml
```
