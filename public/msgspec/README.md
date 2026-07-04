# msgspec

## 用途

`msgspec` 是面向 Python `msgspec` 库的专项 Skill，覆盖 `Struct` 建模、序列化与反序列化、类型验证、约束、标签联合、自定义编码/解码钩子，以及与 `Pydantic`、`dataclasses` 的取舍对比。

## 来源

从 `ruokee/skills-lib` 的 `skills/python/msgspec` 与 `skills/python/msgspec-zh` 引入。

源提交：`d556016`，`feat: add msgspec skills for Python (Chinese and English)`。

## 语言变体

`msgspec` 包含英文（en）变体与中文（zh）变体。

安装脚本后续应支持选择和切换变体；同一个目标目录下同一时间只安装一个 `msgspec` 变体。

```text
├── en/
│   └── msgspec/
└── zh/
    └── msgspec/
```

- `<variant>/msgspec/`：实际安装使用的 Skill 目录
- `references/`：按主题拆分的 msgspec 参考文档
- `examples/`：可运行的完整示例
