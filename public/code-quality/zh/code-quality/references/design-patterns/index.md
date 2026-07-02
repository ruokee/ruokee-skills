# Design Patterns

设计模式是对重复出现的设计问题的词汇，而不是默认就该套用的模板。每个模式都命名了一种解决“变体问题”的形状：某些东西会变化，而模式把这种变化隔离在一个稳定接口之后。代价始终是额外一层间接层。

在套用一个模式之前，先问：

- 这个变化点是真的，还是臆想出来的？抽象了一个从未出现的变化，只会带来纯开销。
- 更简单的构造是否已经足够？在 Python 里，一等函数、`dataclass`、`Protocol`、`match`、decorator、context manager、iterator 和 dispatch map 能吸收或收缩掉很多经典面向对象模式。
- 这个模式是在降低调用方的理解成本，还是只是在多加一跳？
- 失败成本是什么：全局状态、隐藏控制流、类爆炸、更难测试、性能问题，还是生命周期不清晰？

先把问题解决，再决定是否值得为它命名成一个模式。不要先选模式，再反过来找问题去套它。

## 创建型

- [factory.md](factory.md)：Factory Method - 把创建与调用方解耦；在 Python 里常常只是一个函数。
- [abstract-factory.md](abstract-factory.md)：Abstract Factory - 创建必须一起变化的相关对象家族。
- [builder.md](builder.md)：Builder - 一步一步构造复杂对象。

## 结构型

- [adapter.md](adapter.md)：Adapter - 让不兼容的接口协作起来。
- [decorator.md](decorator.md)：Decorator pattern - 通过包装添加行为（与 Python 的 `@decorator` 语法不同）。
- [facade.md](facade.md)：Facade - 复杂子系统之上的简单接口。

## 行为型

- [strategy.md](strategy.md)：Strategy - 稳定接口背后可互换的算法。
- [observer.md](observer.md)：Observer / Pub-Sub - 一对多事件通知。
- [command.md](command.md)：Command - 把请求封装成对象。
- [state.md](state.md)：State - 通过多态状态对象实现状态相关行为。
- [visitor.md](visitor.md)：Visitor - 给稳定的 node type 添加新操作。

## 持久化 / 应用

- [repository.md](repository.md)：Repository - 通过类似 collection 的接口抽象持久化。
- [unit-of-work.md](unit-of-work.md)：Unit of Work - 跟踪变更并原子提交。

关于通用 state machine（不只是 State 模式），见 [../programming-paradigms/state-machine.md](../programming-paradigms/state-machine.md)。
