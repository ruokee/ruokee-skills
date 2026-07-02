# Design Principles

这里是代码质量 review 中使用的设计原则和工程判断框架的参考文档。这些都不是机械规则。它们大多用于管理复杂度、控制变更、保护行为并提升可读性。应把它们当作思考取舍的共享词汇，并结合实际问题的上下文来化解彼此之间的张力。

每份文档都会说明原则是什么、它依赖什么假设、何时适用、何时不适用、最常见的误用方式，以及它如何映射到 Python，而不是 Java 或 C++ 的仪式感。原则之间存在交互或冲突时，相关文档会用文字说明。

请路由到你看到的信号所对应的文档。

|信号|读取|
|-|-|
|重复知识、一个规则在很多地方表达、错误抽象|[dry.md](./dry.md)|
|两个相似案例，不确定是否该抽象|[rule-of-three.md](./rule-of-three.md)|
|不必要的复杂度、脑中要同时持有太多概念|[kiss.md](./kiss.md)|
|投机性特性、没有证明需要的扩展点|[yagni.md](./yagni.md)|
|职责、可替换性、接口宽度、依赖方向|[solid.md](./solid.md)|
|行为应该放在哪里、谁拥有这项责任|[grasp.md](./grasp.md)|
|train-wreck 链、调用方越过远距离对象结构|[law-of-demeter.md](./law-of-demeter.md)|
|调用方把字段取出来再外部决策|[tell-dont-ask.md](./tell-dont-ask.md)|
|inheritance vs composition、mixins、为复用而 subclassing|[composition-over-inheritance.md](./composition-over-inheritance.md)|
|高层逻辑耦合 I/O、time、randomness、外部服务|[dependency-inversion.md](./dependency-inversion.md)|
|test-first、Red-Green-Refactor、behavior specification|[tdd.md](./tdd.md)|
|复杂业务领域、ubiquitous language、bounded contexts|[ddd.md](./ddd.md)|
|抽象深度、information hiding、shallow modules、interface design|[deep-modules.md](./deep-modules.md)|

关于 SOLID 中的依赖方向原则，有两个视角：[solid.md](./solid.md) 作为五项之一来讲，[dependency-inversion.md](./dependency-inversion.md) 则更深入地讨论 Python 中的 DIP 和 dependency injection。做外部 dependency wiring 时两者都要读。

具体的 design patterns（Factory、Strategy、Observer、Adapter 等）放在 `../design-patterns/` 下。这个目录讨论的是何时抽象、何时等待、责任归属以及如何降低变更成本，而不是具体的命名结构。
