# State Pattern (GoF)

GoF State Pattern 通过把状态相关行为委托给多态的 state object，来消除条件逻辑。Context 持有一个当前 State 对象的引用。每个具体 State class 都实现同一接口，提供该状态下特有的行为。State transition 会替换 Context 当前的 state 引用。

这是 state-machine 行为的一种特定 OO 实现。它并不等同于广义上的 state machine - 很多 state machine 用更简单的表示方式会更好：enum + transition table、reducer function、`match`/`case` 或 dispatch map。在决定 State Pattern 是否比更简单的实现更有价值之前，始终先从 [state-machine modeling](../programming-paradigms/state-machine.md) 开始，明确 states、events、transitions、guards 和非法 transition 策略。

## 结构

- Context：维护对 ConcreteState 的引用；委托状态相关请求。
- State（interface/Protocol）：定义状态相关行为的接口。
- ConcreteState：实现某个特定状态的行为；可通过替换 Context 的 state 引用来触发 transition。

## 何时适合这个模式

- 每个 state 都有大量、明确不同的行为 - 不只是返回值不同或者一个 flag 不同。
- state 数量中等，并且相对稳定。
- state-specific 行为足够复杂，拆成 class 之后比平铺条件逻辑更容易读。
- 可以在不修改现有 state class 的前提下新增 state（OCP 收益）。
- state object 需要访问 Context 数据来完成它的行为。

## 何时不适合这个模式

- state 很少，transition 简单，行为差异也不大。transition table 或 `match` 更清楚。
- 工作流主要关心的是 transition permissions 和副作用，而不是多态行为。应使用 transition table。
- state class 退化成围绕单个表达式的一个方法 wrapper - 间接层的成本超过了清晰度收益。
- state 数量增长很快，或者由数据驱动。基于表的方式扩展性更好。
- state transition 需要在一个地方可审计。State Pattern 会把 transition 分散到各个具体 state class 中。

## 常见实现问题

**Transition ownership.** 谁来决定下一个 state？如果由每个 ConcreteState 决定，transition 就会散落在不同 class 中，更难审计。如果由 Context 决定，这个模式又可能退化为 Context 里的条件逻辑。应该在同一个 context 边界内一致地选择一种方式。

**共享 context 数据。** State object 往往需要访问 Context 数据。可以把 Context 显式传给 state method，或者使用共享数据对象。避免通过全局状态或模块级变量形成隐式耦合。

**state identity。** state object 是单例，还是携带每个实例自己的数据？无状态 state object 可以安全共享；有状态的则需要明确的 lifecycle management - 谁创建它们、何时丢弃。

**测试。** 先针对每个 state class 做独立、聚焦的单元测试，再在 Context 层测试 transition。验证非法 transition 被拒绝，而不是静默忽略。

## 区分 State 与 Strategy

[Strategy](strategy.md) 看起来很像 - 两者都把工作委托给多态对象 - 但它变化的是 _算法_，而不是 _生命周期阶段_。如果对象在其生命周期内不会在不同 strategy 之间切换，那它是 Strategy，不是 State。如果主体经历一系列阶段，并且每个阶段行为都不同，那它就是 State。

## 区分 State Pattern 与 state machine

State Pattern 是一种实现技术。state-machine modeling 是一种设计技术。一个 state machine 可以用 enum + transition table、reducer、`match` block、dispatch map、专门的 library，或者 GoF State Pattern 来实现。只有当每个 state 都承载了足够丰富、值得通过多态分发来表达的行为时，State Pattern 才真正值得。

如果你只需要跟踪哪些 transition 合法，并在 transition 时执行副作用 - 但每个 state 并不需要丰富的行为接口 - 那么 [transition table](../programming-paradigms/state-machine.md) 更简单，也更便于审计。

[Command Pattern](command.md) 封装的是请求，而不是状态；当 transition 需要把 commands 排队以便稍后执行时，它与 State 可以很好地互补。
