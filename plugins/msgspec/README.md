# msgspec

## 用途

`msgspec` 是面向 Python `msgspec` 库的专项 Skill，覆盖 `Struct` 建模、序列化与反序列化、类型验证、约束、标签联合、自定义编码/解码钩子，以及与 `Pydantic`、`dataclasses` 的取舍对比。

## 来源

从 `ruokee/skills-lib` 的 `skills/python/msgspec` 与 `skills/python/msgspec-zh` 引入。

源提交：`d556016`，`feat: add msgspec skills for Python (Chinese and English)`。

## 语言变体

`skills/msgspec/` 是完整英文 base，也是 default 变体；`variants/zh/` 是相对 base 的稀疏中文 overlay。

```text
plugins/msgspec/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── skills/msgspec/
├── variants/zh/
├── meta.toml
└── README.md
```

中文 overlay 覆盖英文 base 后，会物化出包含 `references/` 和 `examples/` 的完整中文 Skill。

## 安装

注册仓库 marketplace 后，default 英文版本使用宿主原生命令安装；Pi 直接安装本地 package 路径：

```bash
codex plugin add msgspec@ruokee-skills
claude plugin install msgspec@ruokee-skills --scope user
pi install /path/to/ruokee-skills/plugins/msgspec
```

选择中文变体时，从仓库根目录运行：

```bash
uv run scripts/install.py setup msgspec --scope user --variant zh
```
