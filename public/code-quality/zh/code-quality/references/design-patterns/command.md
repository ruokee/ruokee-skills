# Command

## 目的

把请求封装成对象，这样请求就可以被传递、存储、排队、记录、重放和撤销。发出请求的调用方与知道如何执行它的代码解耦。

## 解决的问题

一次直接调用 - `service.send_email(to, template, context)` - 会立刻执行，并且不留下痕迹。你没法把它放进队列、以后再持久化处理、写进审计日志、在崩溃后重放，或者回滚它。当请求需要拥有超出“调用瞬间”之外的生命周期时，它就必须变成数据。Command 把“做这件事”变成一个你可以持有和检查的值。

## 结构与参与者

- **Command**：携带执行请求所需的一切信息 - 操作及其参数。
- **Receiver**：知道如何完成工作的对象。
- **Invoker**：持有并触发 commands（队列、调度器、菜单、按键绑定）。
- **Client**：创建 commands 并为其配置 receiver。

在经典形式里，command 暴露 `execute()`，有时还会有 `undo()`。关键在于 invoker 统一对待所有 command，而不关心每个 command 具体做什么。

## Python 习惯写法

当 command 需要被排队、序列化或审计时，冻结 dataclass 是最自然的载体：

```python
@dataclass(frozen=True)
class SendEmail:
    to: EmailAddress
    template: str
    context: dict[str, object]
```

一个独立的 handler（或者按 command 类型键控的 `dispatch` map）负责实际工作，让 command 本身保持为普通、可序列化的记录。当 command 不需要持久化、只携带行为时，普通函数或 `functools.partial` 本身就已经是 command 了 - Python 的一等函数足以覆盖最简单的情况。

若要支持撤销，command 必须捕获足够的前置状态来回滚自己，或者和一个 [unit-of-work.md](unit-of-work.md) / memento 配对，以便快照状态。

## 何时使用

- **排队与调度**：放到 job queue 里、重试，或延后执行的任务。
- **撤销/重做**：每个动作都是一个 command，并配一个反向操作；由历史栈驱动撤销。
- **审计轨迹**：每次状态变化都作为 command 记录，用于合规或调试。
- **宏录制 / 重放**：捕获一串 commands 并重新运行。
- **解耦 UI 与动作**：菜单项、按钮和快捷键持有 commands，而不是直接调用 service。

## 何时不要用（过度设计）

- 普通、即时的函数调用已经足够，而且请求既不需要存储，也不需要重放或回滚。把它包成 command class 只是仪式感。
- command 没有稳定 schema，实际上不能被持久化或重放 - 那它带不来任何收益，却要付出构建成本。
- 你为了“解耦”而使用 command 对象，但代码其实只有一个调用方和一个 receiver。

## 失效模式

- **贫血 command + 肥 handler**：逻辑迁移到 handler 里，command 只剩字段袋，dispatch 变成 god function。
- **不稳定的序列化**：持久化 command 在重构后无法反序列化，因为 schema 没有版本化。若要持久化 command，就把它们的形状当作契约。
- **撤销漂移**：`undo()` 不能完美逆转 `execute()`，会悄悄破坏状态。撤销正确性需要明确测试。
- **构造时隐藏副作用**：构建 command 不应执行工作；只有 invoker 才应该触发它。

## 与其他模式的关系

Command 和 [strategy.md](strategy.md) 都是把行为包进对象里，但 Strategy 参数化的是“如何做”（可互换算法），而 Command 参数化的是“做什么”和“何时做”。commands 队列常常与 [observer.md](observer.md) 的事件处理搭配，事件变成要处理的 commands。撤销通常把 Command 与 memento 或 [unit-of-work.md](unit-of-work.md) 结合起来。在 Python 里，每个 command class 都要和普通可调用对象认真比较 - 只有当需要状态、序列化、排队、审计或撤销时，才值得把它做成对象。
