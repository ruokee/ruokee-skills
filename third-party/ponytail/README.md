# ponytail

DietrichGebert 的 `ponytail` 核心 Skill。

## 来源

- 上游仓库：https://github.com/DietrichGebert/ponytail
- 上游路径：`skills/ponytail`
- 引入 ref：`main`
- 引入 commit：`16f29800fd2681bdf24f3eb4ccffe38be3baec6b`
- 引入日期：2026-07-19
- 许可证：MIT，完整条款见 `ponytail/LICENSE.txt`

## 选用原因

这个 Skill 用一组明确的决策阶梯约束编码 Agent：先确认需求是否必要，再依次复用现有代码、标准库、平台原生能力和已有依赖，最后才编写最小实现。它适合减少无必要的抽象、脚手架、依赖和文件数量，同时明确保留安全、可访问性、错误处理和必要验证。

## 引入范围

只保留上游核心 `ponytail` Skill。上游的 `ponytail-review`、`ponytail-audit`、`ponytail-debt`、`ponytail-gain`、`ponytail-help` 以及 hooks、commands、MCP 等插件运行时没有一并引入。

## 本地结构

```text
third-party/ponytail/
├── ponytail/
│   ├── LICENSE.txt
│   └── SKILL.md
├── README.md
└── upstream.toml
```

当前保留原始 Skill 内容，未做本地改写。
