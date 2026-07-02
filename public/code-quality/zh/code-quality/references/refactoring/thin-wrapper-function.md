# Thin Wrapper / Trivial Helper

## 它是什么

thin wrapper 是一个函数，它的整个函数体只是转发到另一个函数、给一次调用改名，或者包裹一个单独表达式 - 却没有增加任何语义价值。它既没有隐藏复杂度，也没有建立边界，更没有强制不变量。它只是多了一个名字和一层。

```python
def get_user_name(user):
    return user.name  # adds nothing the caller couldn't see

def fetch_data(url):
    return requests.get(url)  # renames one call, hides nothing
```

这个 smell 说的不是“这个函数很短”。很多短函数都非常好 - 一个命名准确的一行函数，如果能抓住领域概念（`is_eligible_for_refund`），那它就物有所值。这个 smell 说的是 _没有增加意义_：这个 wrapper 付出的代价是名字、一次跳转和一个栈帧，换回来的却什么也没有。

这个 smell 在 agent 生成的代码里尤其常见，因为“去重”或“提升可读性”的本能，常常会制造出一堆一行 helper，每个都只转发一个调用。结果是你得在很多定义之间来回追着看，才能理解代码；而如果一开始直接看内联表达式，反而更清楚。它和 `duplicated-code.md` 里说的错误 DRY 失败模式，以及 `../design-principles/dry.md` 密切相关。

## 什么时候 wrapper 有价值

当 wrapper 做的不只是转发时，它就值得保留：

- **围绕不稳定实现的稳定接口。** 如果被包装的库、API 或内部模块未来很可能会变，那么 wrapper 可以把变化集中到一处。这就是 Adapter 的思想 - 见 `../design-patterns/` - 而这里看起来很薄的 wrapper，实际上是一个 surface 很小但很深的模块。
- **测试 seam。** 一个之所以存在、是为了让调用方可以用 fake 来测试，或者让依赖可以注入的函数，即使函数体很简单，也提供了可替换边界。见 `../design-principles/dependency-inversion.md`。
- **横切关注点。** 增加日志、重试、缓存、指标或 transaction boundary 的 wrapper 确实在添加行为。这些是 decorator，不是 thin wrapper。
- **命名的领域概念。** `requires_tax_review(order)` 包裹一个布尔表达式，会让规则可搜索，并给它一个明确归宿。这个名字本身就是价值。

## 什么时候它只是噪音

- 只有一个调用方，而且没有抽象边界 - 那就 inline 掉。
- wrapper 名字只是 wrapped call 的同义词（`fetch_data` 对应 `requests.get`），没有任何领域意义。
- 它只是把参数原样转发给一个同样清晰命名的函数。
- 它只是因为样式规则说“提取函数”，而不是因为读者真的需要它。

修法是 [inline-function.md](./inline-function.md)：把函数体折回调用方，然后删掉这个 wrapper。

## Python 专属说明

Python 里的函数调用不是免费的。每次调用都会创建 frame，解释器也确实要为此工作。对大多数代码来说这不重要 - 清晰度更重要。但在热点路径和紧密循环里，围绕逐元素操作的一层层 thin wrapper 可能会出现在 profile 里。这只是避免它们的次要理由，绝不是主要理由：最主要的成本永远是间接层带来的认知负担，而这个间接层却什么都没换来。

## 如何判断

问自己：如果我删掉这个函数，并把它的函数体在每个调用点都内联进去，代码会更难理解，还是更难修改？如果答案是否定的，那它就是 thin wrapper。如果删掉它会让调用方暴露给不稳定依赖、把一个领域规则散得到处都是，或者破坏一个测试 seam，那它就在做真正的工作 - 留着它。判断标准是它保护的边界，而不是它有多少行。
