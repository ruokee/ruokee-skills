# Docstrings And API Docs

一旦类型标注承担了静态契约，docstring 的职责就变了。它不再是记录参数类型和返回类型的地方 - signature 已经以可机器检查的方式做到了这一点；把这些内容再写一遍，只会制造第二份容易漂移的副本。docstring 的职责是 signature _无法_ 表达的东西：函数在领域中的含义、它承诺什么和假设什么、它会碰到外界什么，以及如何正确使用它。核心能力在于把每一条信息放到属于它的地方，并且只有在它能补充读者无法从其他地方直接看到的信息时才写 docstring。

## 信息该放在哪里

现代 Python API 会把文档分散到多个表面上，而大多数文档问题其实都是放置问题 - 事实放错位置，或者同一事实写了三遍。对任何信息来说，第一步不是“怎么措辞”，而是“哪个表面负责它”。

|信息|所属表面|原因|
|-|-|-|
|参数和返回值 _类型_|Signature / annotations|可机器检查、IDE 可读；写进 docstring 会漂移|
|领域含义、业务规则|Docstring|类型系统无法表达值 _意味着_ 什么|
|取值范围、单位、形状、dtype|Docstring 或 `Annotated`/`Field`|取决于是否需要机器读取|
|跨参数约束|Docstring 或 validator|单个 annotation 无法关联两个参数|
|副作用、资源生命周期|Docstring|调用者必须知道 IO、网络、DB、全局状态|
|异常语义|Docstring|Python 类型无法表达“raises”|
|机器可读的字段约束|Schema metadata（`Field(...)`）|供验证和生成 API 文档使用|
|例子|Docstring、README 或测试|最好还能执行，这样不会腐烂|
|版本变更、弃用|Release notes、`warnings.deprecated()`|同时服务读者、checker 和 runtime|

最常见的错误，是重复一条更权威的表面已经拥有的事实 - 例如在 prose 里写 `min_length=3`，而 `Field(min_length=3)` 已经声明过，或者把 annotation 已经给出的类型再写一遍。

## 何时 docstring 有价值

当 docstring 告诉读者的是 signature 无法表达的内容时，它才配得上自己的位置。最清晰的信号有：

- **语义。** 返回值 _意味着_ 什么？`-> str` 只说明它是字符串；docstring 会说明它是“适合做 case-insensitive lookup 的 normalized form，而不是 display name”。
- **类型无法承载的约束。** 必须是奇数的 window、不能为空的 list、必须是 UTC 的 timestamp - annotation 只写了 `int`、`list`、`datetime`，docstring 才承载剩余信息。
- **副作用。** 除返回值之外的任何可观察行为：database write、network call、被修改的参数、被填充的 cache、创建的文件。调用者需要这些信息才能安全地使用函数，而 annotation 看不出来。
- **异常语义。** 调用者预期应处理哪些异常，以及它们意味着什么 - 不需要列出一切可能冒泡的异常，而是契约中的那几个。

```python
def normalize_username(raw: str) -> str:
    """Return a normalized username for account lookup.

    Leading and trailing whitespace is stripped and the result is
    case-folded, so it is suitable for case-insensitive comparison. The
    result is not guaranteed to be a valid display name.
    """
    return raw.strip().casefold()
```

这里 `raw: str -> str` 已经写在 signature 里；docstring 增补的是 lookup 语义、case-folding 规则，以及明确限制（“不是 display name”）。差的版本只会重复函数名（“Normalize username”）或重复 signature（`raw 是 str，返回 str`）。

## 何时 docstring 是噪音

如果 docstring 只是在重复 signature，那它比没有还糟 - 它增加维护成本，并制造一份最终会与第一份冲突的真相副本。以下情况应跳过或缩短 docstring：

- 它只会重复 annotation 已经给出的类型（`user_id (str): the user id`）。
- 它只会重复函数名（`def save_user(...): """Save a user."""`）。
- 它是一个很小的私有 helper，名字和 signature 已经说明了一切。
- 它会重复 schema metadata 已经声明的约束。

基于 coverage 的 docstring 强制要求（“每个函数都必须有 docstring”）往往正会制造这种噪音。linter 可以检查 docstring _是否存在_、section 是否规范；但它无法判断 docstring 是否真的有内容。应当把 docstring lint 当作低层次卫生门槛，而不是文档质量的证明。

## Docstring 风格

有三种风格被广泛使用，这个 skill 不强制某一种 - 选择应当跟项目的文档需求走，而不是跟风潮走。

- **Google style** 使用 `Args:`、`Returns:`、`Raises:` 等 section。它轻量、易读，适合通用工程 API 和后端服务。在有完整类型标注时，section 里省略类型（`host: the bind target`，而不是 `host (str): the bind target`）。
- **NumPy / numpydoc style** 使用带下划线的 section（`Parameters`、`Returns`、`Notes`、`Examples`）。它结构更强，适合科学和数据 API，因为 shape、dtype、units、数学定义和例子都很重要。对简短的业务 helper 来说则过于重型。
- **reStructuredText / Sphinx** 使用 field list（`:param x:`、`:returns:`），并与 Sphinx 文档站、cross-reference 和 version directives 集成。它适合公开发布的 library 和 framework；对内部代码来说，其语法噪音大于收益。

无论采用哪种风格，只要有 annotation，规则都不变：不要把类型写进 prose。让 signature 负责类型，让 docstring 负责含义。

## 基于 schema 的文档

对于基于 Pydantic 和 FastAPI 等工具构建的 web API 和 data model，类型标注和 field metadata 会成为验证、序列化 _以及_ 生成文档的单一事实来源。字段类型、约束（`Field(gt=0, le=100)`）和描述（`Field(description=...)`）都会进入生成的 OpenAPI / JSON schema。在这种世界里，docstring 的地盘缩小到 schema 无法表达的部分 - 更高层的业务语义、事务行为，以及跨字段关系：

```python
class CreateOrderRequest(BaseModel):
    sku: Annotated[str, Field(min_length=3, description="Public stock keeping unit.")]
    quantity: Annotated[int, Field(gt=0, le=100, description="Units requested.")]
```

约束和每个字段的描述都放在 `Field(...)` 中，直接进入 schema。endpoint 上的 docstring 则解释这个 operation _做什么_ - “在写入订单前先预留库存；如果预留失败，则不会创建订单” - 这是任何 field metadata 都无法表达的。需要防止的失败模式，是把同一句话同时维护在 `Field(description=...)`、model docstring 和手写 OpenAPI description 里。选定一个事实来源，其余内容只做引用。

## 文档站与 docstring

docstring 只能文档化一个 object；它不能替代文档站。教程、how-to guide、设计 rationale 和迁移说明都是叙事型文档，单靠任何数量的 per-function docstring 都拼不出来。像 Sphinx 加 `autodoc` 这样的工具可以把 docstring 拉进 API reference，但自动生成的 reference 并不等于高质量文档 - 叙事部分仍然必须人工编写。一个实际的注意事项：`autodoc` 会 import module 来读取它，因此任何 import-time side effect 都会在文档构建过程中执行；保持 module import 干净（也就是 [structure](../project/structure.md) 所要求的那种纪律），文档构建就会保持可预测。
