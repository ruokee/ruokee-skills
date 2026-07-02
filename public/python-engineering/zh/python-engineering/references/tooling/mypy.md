# mypy

mypy 是 Python typing 生态里成熟、参考性最强的 static type checker。当项目需要一个严格、广为理解的 gate、广泛的第三方 stub 支持，或需要与开源社区更一致时，它是自然选择。

## Strict Mode

`--strict` 会打开一组选项，合起来要求完整的注解覆盖，并拒绝渐进式 typing 原本可能留下的静默缺口：`disallow_untyped_defs`、`disallow_any_generics`、`warn_return_any`、`no_implicit_optional`、`warn_unused_ignores` 等。对于新项目，起步时直接启用 strict mode 成本很低；把它后加到一个未标注的代码库上，真正的工作量才会显现。

```toml
[tool.mypy]
strict = true
```

## 渐进式采用

mypy 本身就是为渐进式 typing 设计的，因此很适合在现有代码库上逐步采用。可以先放宽，再按 module 逐步收紧，通过 per-module override section 在已有 annotations 的地方先提高严格度，再推进到未标注区域。

```toml
[[tool.mypy.overrides]]
module = "legacy.*"
disallow_untyped_defs = false
```

## 插件系统

mypy 支持 plugin，用来教它理解 framework-specific 的语义，而这些语义 core type system 本身无法表达。ORM、data-modeling library 和其他会动态生成属性或变换 class 的 framework 都有对应 plugin。plugin 正是让 mypy 理解一个 dataclass-like 构造、而不是把它视作黑箱的方式。

## 常见痛点

反复出现的摩擦点是第三方 stub：某个 dependency 可能根本不提供类型信息、只提供不完整 stub，或者需要单独安装 `types-*` package，而缺失 stub 会迫使你在安装它们、自己写本地 stub，或忽略该 module 之间做选择。条件 import（`TYPE_CHECKING` 块、版本条件 import、可选 dependency）也是另一个常见困惑来源。若要 suppress 某个错误，应写出具体错误码和理由，而不是直接写裸 `# type: ignore`，这样 suppression 才保持可审计。

## 何时比 ty 更有价值

当项目需要与开源生态对齐、匹配现有代码库的历史、兼容外部贡献者的习惯，或要锁定某个细微的类型行为差异时，mypy 才会体现价值。在 [ty](ty.md) 因其速度和 editor 集成而成为默认 gate 的地方，mypy 的价值在于成熟度和生态覆盖。对于正在发布的 library，或者必须与上游期望一致的迁移，常常会选择在默认设置之外或替代默认设置，启用一个 mypy strict profile。

## 与其他 checker 的关系

mypy、[ty](ty.md) 和 [basedpyright](basedpyright.md) 都检查同一套 type system，但在成熟度、严格度和速度上不同。它们在棘手的 inference 场景中偶尔会给出不同结果。对于个人项目，长期同时开着三道 gate 的配置成本通常不值得；只有在 library 发布、外部协作或迁移窗口中，才让额外 checker 发挥交叉验证的价值。
