# Declarative Programming

## 它是什么

Declarative programming 描述的是你**想要什么**，也就是目标、约束、data 的形状，并把**怎么做**留给 framework、library 或 engine。你写的不是步骤，而是一段描述，然后让别的东西去执行它。SQL 是最典型的例子：你陈述想要的 result set，由 query planner 决定如何生成它。Configuration files、schemas、routing tables、CLI argument definitions、validation rules 和 rule engines 都是 declarative 的。

在 Python 项目里，declarative style 的出现频率比很多人意识到的更高：`pyproject.toml`、`dataclass` 的 field list、`TypedDict`、`argparse` parser、web framework 的 route decorators、permission table、state machine 的 transition table。它们本质上都是 data，由某个 engine 来解释，而不是需要你逐步执行的代码。

## 其背后的假设

- 有些结构作为 _data_ 比作为 imperative code 更容易检查、组合和文档化。
- framework 或 library 可以接管重复的执行逻辑，于是你的代码只需要表达与默认行为不同的部分。
- 当规则稳定、执行模型清晰时，以声明的方式表达它们可以减少 boilerplate，并集中 single source of truth。

## 何时适用

- 项目和工具配置：`pyproject.toml`、Ruff、pytest、pre-commit。
- Schema 和 type 定义：`dataclass` fields、`TypedDict`、Pydantic / FastAPI models、序列化元数据。
- 由 framework 执行的结构定义：CLI 参数、web routes、permission tables、mapping tables、transition tables。
- Queries 和 transformations：SQL、query builders、declarative data mappings。

共同点是：有稳定的结构、明确的执行引擎，并且能从一个可检查的 single source of truth 中受益。

下面是一个从 imperative 到 declarative 的小例子。Imperative dispatch：

```python
def handle(event: str) -> None:
    if event == "submit":
        do_submit()
    elif event == "pay":
        do_pay()
    elif event == "cancel":
        do_cancel()
    else:
        raise ValueError(event)
```

Declarative dispatch —— mapping 本身就是 logic，而一个很小的 engine 来应用它：

```python
HANDLERS: dict[str, Callable[[], None]] = {
    "submit": do_submit,
    "pay": do_pay,
    "cancel": do_cancel,
}

def handle(event: str) -> None:
    try:
        HANDLERS[event]()
    except KeyError:
        raise ValueError(event) from None
```

Declarative 形式把所有 case 一次性放在一起，便于查看，易于扩展，也可以作为 data 被检查、计数和测试。代价是，“什么时候运行什么” 现在多了一层间接性，这正是下一节要谈的 tradeoff。

## 什么时候会变成问题

- 真正的 control flow 被藏在 declaration 后面，但执行顺序和错误位置变得不可见。当 declarative pipeline 失败时，stack trace 指向 framework internals，而不是你的意图。
- Configuration 逐渐长成了一门 programming language：在 YAML 或 TOML 里写 conditionals、loops 和 templating，却没有语言应有的工具支持。
- 为了“灵活性”构建了一个 DSL 或 extension point，但实际上只有一个 call site。这是 speculative structure；见 [../design-principles/yagni.md](../design-principles/yagni.md)。
- 调试需要理解 engine 的 evaluation model，而这个 model 文档不足或者出人意料。

Declarative style 用 explicit control flow 换取简洁。只要 engine 可信、结构稳定，这种交换就值得；但当你需要看到并逐步执行实际发生的事情时，它就是有害的。

一个实用的判断标准：如果新人问“这运行起来会发生什么”，而诚实的答案必须先解释 engine 的 evaluation model 才能回答，那就说明 declaration 吸收了太多 logic。Declarations 应该描述 _facts 和 structure_；一旦它们开始描述 _sequence 和 decisions_，通常就是该退回到 explicit code 的信号。

## 在 Python 中

- 为每种 declarative structure 提供单一事实来源。不要把 schema 为 type checker 写一遍、为 runtime validation 再写一遍、在 docs 里又写第三遍，能推导就推导，能生成就生成。
- 在边界处把外部 config 解析成 typed object（`dataclass`、Pydantic model），然后让其余代码使用具体类型而不是原始 dict。见 [data-oriented.md](./data-oriented.md)。
- 复杂的 rule tables 仍然需要测试。Declarative 不代表可以不要测试；transition table 或 permission matrix 值得覆盖它的各行和拒绝的 case。
- 对那些会隐藏 control flow 的 declarative 机制——decorators、route registration、signal handlers——要确保真实的 execution path 仍然可以被追踪。见 [event-driven.md](./event-driven.md)，那里讨论了 invisible wiring 的相关风险。
- 保留一个 imperative escape hatch。最好的 declarative 设计会让少数不规则情况回退到普通代码，而不是逼所有例外都塞进 declaration 的词汇表里。一个把路径映射到 handlers 的 routing table 仍然是 declarative；一个开始长出 `condition` mini-language、用来表达“仅在星期二且仅对 premium users” 的 routing table，已经开始糟糕地重造 programming language 了。声明常规情况，把不规则情况交给普通函数处理。

## 与其他 paradigms 的关系

- [state-machine.md](./state-machine.md) 的 transition table 是 declarative 的：合法移动是 data，由一个小 engine 来应用它们。
- Declarative config 为 imperative shell（[imperative.md](./imperative.md)）提供输入，后者读取它并执行。
- Declarative 和 data-oriented design 有大量重叠：两者都把 structure 当作可检查的 data，而不是 behavior。区别在于强调点不同——declarative 是把 execution 交给 engine，data-oriented 是把 data 本身建模好。
- “更 declarative” 从来不是目的本身。目标是让 rules 和 data shapes 成为中心、可检查、可文档化的东西。当一个 declaration 不再像一个事实，而开始隐藏一个 decision 时，这就是该向 explicit code 后退一步的信号。
