# Observer / Pub-Sub

## 目的

让一个对象（subject）在状态变化或事件发生时通知多个依赖者（observer），而 subject 不必知道它们是谁。它建立起一种运行时可变化的一对多依赖。

## 解决的问题

当系统中的多个部分都必须对某件事作出反应 - 缓存要失效、UI 要刷新、审计日志要记录 - 如果把源头直接调用每个响应者，源头就会和所有响应者耦合。再加一个响应者，就得改源头。Observer 把这件事反过来：响应者订阅，源头只负责发布。

## 结构与参与者

- **Subject / publisher**：持有订阅列表并发出通知。
- **Observer / subscriber**：注册关注并处理通知。
- **Event**：描述发生了什么的载荷。

在 Python 里，subject 常常是一个按事件类型键控的 event bus：

```python
class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type[Event], list[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: type[Event], handler: Callable[[Event], None]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event: Event) -> None:
        for handler in list(self._subscribers.get(type(event), [])):
            handler(event)
```

## 需要显式决定的设计问题

Observer 实现最容易出错的地方就在这里。下面这些都没有唯一正确答案，但每一个都必须是有意识的选择，而不是偶然如此。

- **订阅者生命周期**：谁来取消订阅，什么时候取消？超过订阅者生命周期的订阅会泄漏内存，并让已死对象继续存活。可以考虑对 handler 使用 `weakref`，或者显式返回一个 unsubscribe handle / 使用 context manager。
- **错误传播**：如果一个 handler 抛错，后面的 handler 还继续运行吗？吞掉错误会隐藏 bug；直接传播会让一个坏订阅者打断整个 publish。要决定并写清楚 - 常见做法是：每个 handler 单独隔离错误、记录日志、继续执行。
- **顺序**：订阅者是按注册顺序执行，还是顺序未定义？不要让调用方依赖顺序，除非你明确保证它。
- **重入**：handler 在分发过程中能否 publish、subscribe 或 unsubscribe？像上面那样遍历订阅列表的副本，可以避免“遍历中修改”导致的问题。
- **同步 vs 异步**：同步的进程内通知最简单。对于 `async` handler，你必须选择顺序 `await` 还是 `asyncio.gather`，以及如何处理阻塞或永远不完成的 handler。

## 何时使用

- 多个独立响应者必须对一个事件作出响应，而且响应者集合会变化，或者源头并不知道它们是谁。
- 你想把领域动作与其副作用（邮件、指标、缓存）解耦。
- 关系确实是一对多，并且是动态的。

## 何时不要用

- 只有一个固定响应者 - 直接调用它。event bus 只会增加间接层，并在没有解耦收益的地方隐藏控制流。
- 严格顺序和清晰的串行工作流比解耦更重要 - 显式 pipeline 更清楚。
- 需要跨进程交付：进程内 Observer 不提供投递、重试或持久性保证。应使用真正的消息系统（queue、broker）并定义好语义。

## 失效模式

- **隐藏控制流**：一次 `publish` 会触发一连串效应，而从调用点根本看不出来。
- **内存泄漏**：忘记取消订阅会让引用永久保留。
- **意外重入**：handler 在分发中途修改 subject，破坏迭代。
- **静默失败**：被吞掉的异常意味着事件“发生了”，但它的效果却从未真正产生。

## 与其他模式的关系

Observer 在事件被实体化为可排队或重放的对象时，会与 [command.md](command.md) 重叠。[mediator] 的协调姿态正相反：Mediator 把交互逻辑集中起来，而 Observer 则把它分发出去。对于跨进程 fan-out，这个模式会让位于消息 broker 基础设施，而不是内存中的 bus。
