# Strategy

## 目的

在一个稳定接口背后定义一组可互换的算法，这样就可以在配置阶段或运行时选择并切换算法，而无需修改使用它的代码。

## 解决的问题

当某个操作有多个变体算法（排序、评分、定价、路由、重试、压缩等）时，如果把它们塞进不断增长的 `if/elif` 里，就会让调用方耦合到每个变体，并且新增一个变体就意味着要修改共享代码。Strategy 把每个算法隔离开来，使调用方只依赖“某个评分 item 的东西”，而不依赖具体评分规则。

## 结构与参与者

经典形式里有一个 **context** 持有对 **strategy** 接口的引用，多个 **concrete strategies** 实现这个接口。context 把工作中可变的那部分委托给注入的 strategy。context 负责稳定的工作流；strategy 负责变化的部分。

## Python 形式

Python 的函数是一等公民，所以 Strategy 往往只是一个函数参数。通常并不需要 strategy class：

```python
def rank_items(items: list[Item], score: Callable[[Item], float]) -> list[Item]:
    return sorted(items, key=score, reverse=True)

def priority_score(item: Item) -> float:
    return item.priority

rank_by_priority = partial(rank_items, score=priority_score)
```

按重量大致从轻到重的形式：

- **普通函数或 `lambda`** 作为参数传入 - 最轻量的 strategy。
- **closure** 用来捕获少量稳定配置，或者用 `functools.partial` 预绑定参数，得到更窄的 callable。
- **`Protocol` 或可调用对象**：当 strategy 需要状态、多个相关方法，或者一个能表达意图的名字时使用。
- **`functools.singledispatch`**：当 strategy 是按输入的 _类型_ 而不是配置值来选择时使用。
- **dispatch map / `match`**：当选择依赖配置值或若干条件时使用。

## 何时使用

- 现在就有多个真实算法，而且调用方不应该知道当前运行的是哪个。
- 算法必须在运行时可选（用户选择、配置、A/B 测试）或能在测试中替换。
- 变化沿着一个清晰的轴展开（“如何评分”），接口很小且稳定。

## 何时不要用

- 只有一个算法，或者一个 `if` 就能覆盖两个情况。预先“strategy 化”只会平白增加一个接口。
- strategy 接口过宽，以至于调用方必须组装一个复杂对象才能只改变一个决策 - 这说明抽象切得不对。
- 这些“strategies”其实差异在于它们需要什么数据，而不只是怎么计算 - 它们未必共享一个连贯的接口。

## 失效模式

- 一个只有一个方法、只有一个实现的 `Strategy` class，本来一个函数就能更少仪式地说清楚。
- 过宽的接口迫使每个 concrete strategy 去实现一些只有其中一个会用的方法。
- strategy 选择散落到代码各处，而不是在一个地方（factory 或 dispatch map）解决，这样新增变体时就得四处搜索选择点。

## 与其他模式的关系

[factory.md](factory.md) 常常负责 _选择_ 用哪个 strategy。[command.md](command.md) 在结构上很像（把行为装进对象），但它的意图是把请求保存下来以便以后执行，而不是变换算法。[state.md](state.md) 模式看起来像 Strategy，但它的变体会在事件中 _改变自己_，而不是由调用方选择。`functools.singledispatch` 和 pattern matching 是 Python 中最常吸收 Strategy 的机制。
