# Structural Pattern Matching

`match`/`case`（Python 3.10+，[PEP 634](https://peps.python.org/pep-0634/)）按值的 _形状_ 对其进行解构，并从匹配部分中绑定名字。它是一种对结构化数据进行分解的声明式方式，而不是 `if`/`elif` 的装饰性替代品。

## 它是什么

`match` 语句将一个 subject 值与一系列 pattern 进行比较。第一个匹配成功的 pattern 会执行其块；pattern 中的名字会绑定到 subject 对应的部分。与很多语言中的 `switch` 不同，这里的 case 不是常量标签 - 它们是可以同时检查类型、结构和内容的 pattern。

```python
match command:
    case "quit":
        stop()
    case ["move", direction]:
        move(direction)
    case {"action": action, "target": target}:
        dispatch(action, target)
```

pattern 不会 fall through。要么恰好执行一个块，要么在没有匹配且没有兜底分支时什么也不执行。

## 语法形式

Literal pattern 用相等性匹配常量（`case 0:`、`case "quit":`、`case None:`）。`True`、`False` 和 `None` 按 identity 匹配。

Capture pattern 是一个裸名字；它总是匹配并绑定 subject（`case x:`）。裸 `case _:` 是 wildcard - 它匹配任何值但不绑定任何东西，作为默认分支。

Value pattern 使用带点的名字，因此读取的是命名常量而不是重新绑定：`case Color.RED:`。裸名字会 capture；加上点才表示比较。

Sequence pattern 按长度和位置匹配 list 和 tuple，`*rest` 可以吸收中间或尾部：`case [first, *rest]:`。它匹配任何 `Sequence`，但不包括 `str`、`bytes` 和 `bytearray`。

Mapping pattern 匹配指定 key 并忽略其余部分：`case {"action": action}:`。`**rest` 会捕获剩余键值对。缺少 key 会导致匹配失败。

Class pattern 匹配类型和属性：`case Point(x=0, y=y):`。像 `Point(0, y)` 这样的 positional sub-pattern 依赖 class 的 `__match_args__`；keyword sub-pattern 则不依赖。

OR pattern 从左到右尝试多个备选：`case "y" | "yes":`。每个备选都必须绑定相同的名字。

Guard 会在 pattern 结构上匹配成功后再运行布尔条件：`case [x, y] if x == y:`。guard 失败会继续尝试下一个 case。

pattern 可以自由嵌套，因此 `case Response(status=200, body={"items": [first, *_]}):` 可以在一个表达式里同时匹配类型、属性值、嵌套 mapping key 以及非空序列。

## 何时优于 if/elif

当分支依赖于数据的 _结构_ 而不是单个标量时，`match` 才有价值：

- 解析或遍历异构树（AST nodes、JSON-like 文档、protocol messages）。
- 按结果的形状进行分派：不同长度的 tuple、带特定 key 的 mapping、某个 class 的实例与另一类实例。
- 类代数式处理，其中每个 variant 都是不同的 dataclass，而且每个 case 提取的字段也不同。

在这些情况下，替代方案通常是一串 `isinstance` 检查加上手工索引和 `.get()` 调用。`match` 将类型检查、结构检查和提取合并到一个可读块中，并且只在变量有效的分支上绑定名字。

## 何时不该用

`match` 往往比表面看起来更不合适。以下情况更适合简单方案：

- 分派发生在单个值上，且结果集合已知。把 key 映射到 handler 的 dict（`handlers[key]()`）更清晰、可在运行时扩展，也便于单独测试。不要用一长串 literal case 的 `match` 来替代它。
- 逻辑只是一个很小的布尔判断。两三个普通条件用 `if`/`elif` 更清楚；`match` 会带来额外仪式感，却没有可利用的结构。
- 你在建模 state machine。transition table - `(state, event) -> next_state` - 可以把 states 和 transitions 作为数据来枚举、验证和绘图。`match` 会把这些 transition 藏进 control flow，使你无法一眼看到整张图。为什么显式 transition 很重要，见 [state machine modeling](../../../code-quality/references/programming-paradigms/state-machine.md)。

经验法则是：如果没有可解构的结构，`match` 大概率就是不合适的选择。

## 完备性

Python 在运行时不会强制完备性 - 未匹配的 subject 只是静默落空而不会报错，这可能掩盖 bug。可以通过两种习惯来应对：

- 添加显式 `case _:` 并在 unexpected value 到达时抛错，把静默 fall-through 变成 loud failure。
- 让 type checker 推理完备性。当匹配的是 closed set，如 `Enum` 或 dataclass 的 union 时，checker 可以指出缺少的 case。把 match subject 与默认分支里的 `assert_never(unreachable)` 配合使用，可以把预期的完备性显式化，并让 checker 证明它。

这种组合 - closed type 加 `assert_never` - 才能把 `match` 从便利工具变成可检查契约。

## 典型用途

好：把解析后的 message 解构成命令 variant；处理小型 AST 的每种 node type；匹配 `(status, payload)` 的结果形状；用 mapping 和 sequence pattern 展开嵌套配置结构。

差：替代 dict 查找；表达双向布尔逻辑；编码状态转移；仅仅为了调用对象本可多态暴露的方法而对运行时类型做匹配。

还有一个隐蔽成本：在 `case` 中绑定的名字在 `match` 块结束后仍然可见，所以过于宽泛的 capture pattern 可能泄漏出令人意外的绑定。除非 positional 顺序是类型契约中稳定且有文档保证的一部分，否则优先使用具体 pattern 和 keyword sub-pattern，而不是 positional ones。
