# Tell, Don't Ask

Tell, Don't Ask 说的是：不要先把数据从对象里取出来，再从外部对它做决策；而是把决策推回拥有这些数据的对象里。告诉对象你想让它做什么，不要先问它内部是什么，然后替它行动。

这个原则关注的是 _行为相对于所依赖数据的放置位置_。当数据和治理它的规则待在一起时，规则可以依赖对象维护的不变量，而这些规则的变化也只有一个落点。当调用方反复读取字段并在外部拼装规则时，逻辑就会四处分散，对象也无法保护自己的 consistency。

## 问题的形状

“Ask” 风格的代码从外部读取 state，然后再根据 state 分支：

```python
# Ask: caller pulls data out and decides
if account.balance >= amount and not account.is_frozen:
    account.balance -= amount
    account.last_debit = now()
```

每一个给 account 扣款的 caller 都必须记住相同的检查和相同的记账细节。如果出现新规则（透支额度、冻结、审计日志），每个地方都要更新，任何一个遗漏都会让 account 进入非法状态。

“Tell” 风格则把决策移到内部：

```python
# Tell: object owns the rule and its invariants
account.debit(amount)   # raises if frozen or insufficient
```

现在 account 自己负责维护不变量。调用方只表达意图。规则只有一个落点，而对象也不会通过这条路径被驱动到不一致状态。

## 与封装的关系

Tell, Don't Ask 是从调用方角度看封装。Encapsulation 说对象应该隐藏内部 state；Tell, Don't Ask 说调用方根本不该需要这些 state——它们应该把一个 command 交给对象，并相信对象会维护自己的 invariants。这两者互相强化：一个用行为而不是原始 state 来暴露自己的对象，会让数据保持私有且有意义。

它也与 GRASP 的 [Information Expert](./grasp.md) 启发式重叠（把责任分配给掌握完成责任所需信息的类）以及 [Law of Demeter](./law-of-demeter.md)（不要越过结构去做外部决策）相呼应。三者都在把行为往数据所在处推。

## 什么时候 asking 是合适的

Tell, Don't Ask 是用于保护拥有行为的对象 invariants 的启发式。它不是禁止读取数据。以下场景中 asking 是正确的：

- **查询和报表。** 计算总计、聚合和汇总，本质上就是读取多个对象里的多个字段。硬把这类逻辑塞进每个对象的 command method 会扭曲模型。
- **序列化和 DTO。** 把对象转换成 JSON、row 或 wire format，本来就是纯数据访问。data transfer object 或 API schema 就应该清晰暴露字段。
- **UI 渲染。** 显示代码读取 model state 来绘制界面。这就是它的工作；它并没有替模型做业务决策。
- **Read model。** 在读写分离系统中，read side 本来就应该是 data-oriented 且透明的。

判别标准是：调用方是在 _决定对象本应拥有的某件事_（业务规则、状态迁移、invariant），还是在 _报告 / 转换 / 展示_ 真正属于自己职责的数据？前者是 Tell, Don't Ask 违规，后者则是正常且健康的。

## 常见错误

- **消灭所有 getter。** 有些人把这个原则理解成对象绝不能暴露数据。这会破坏报表、序列化和 UI，并制造命令-only 模型。查询是可以的。
- **把行为塞进 DTO 和 dataclass。** 纯数据载体应该保持纯数据载体。把 domain command 加到 transport object 上，会模糊边界，并让它和自己不该知道的规则耦合。只有当这些数据本身需要保护 invariants 时，才给它加行为。
- **把昂贵工作藏在看起来无害的 property 后面。** 一个会触发 I/O 或重计算的 `property` 会让调用方意外，因为他们原本以为属性访问是廉价的。Tell, Don't Ask 关心的是让行为靠近数据，而不是把副作用伪装成属性读取。

## 在 Python 中

- 给 domain object 提供有语义的 command method：`invoice.mark_paid()`、`order.cancel()`、`account.debit(amount)`。这些方法在内部维护状态迁移和 invariants。
- 让数据载体、API schema、ORM row 和 config object 明确暴露 attributes。
- 用 `property` 统一存储值和派生值，但要保持廉价且无副作用——不要把 I/O 藏在里面。
- 在 functional core 中，行为不一定非得是 method：一个接受数据并返回决策的命名函数（例如 `def can_debit(account, amount) -> bool`）也能把 logic 和 data 放在一起，而无需强行面向对象。Tell, Don't Ask 关心的是把规则和数据放在一起，而不是坚持必须用 method。
