# Programming Paradigms

这些参考文档描述的是在代码质量 review 中会遇到的编程范式和执行模型。Python 是一门 multi-paradigm 语言：functions、modules、objects、types、protocols、resource lifecycles 和 async tasks 都是可以组合使用的工具。这些文档的目的，是帮助你判断某个问题更适合哪一种 paradigm，而不是强行推行单一的内部风格。

一种常见的失败模式，尤其是在 agent 生成的代码里，是先选 paradigm，再把问题硬塞进去：要么一切都变成 class，要么一切都变成 higher-order functions 的链条，要么任何 workflow 都变成一团隐式的 boolean flags。更好的做法，是先读出问题的形状，再去拿那个默认假设最贴近它的 paradigm。

每篇文档都会说明这个 paradigm 是什么、它依赖什么假设、何时适合、何时不适合、常见误用方式，以及它如何落到 idiomatic Python。不同 paradigms 彼此交互时，相关文档会在正文中说明。

请跳转到与你正在看的内容相匹配的文档。

|信号|读取|
|-|-|
|逐步状态变更、脚本、orchestration、entry points|[imperative.md](./imperative.md)|
|描述 what not how - config、schema、routing、rule tables|[declarative.md](./declarative.md)|
|长生命周期、带状态的实体、polymorphism、framework extension|[object-oriented.md](./object-oriented.md)|
|难以测试的 logic 与 I/O、时间、随机性、外部调用混在一起|[functional-core.md](./functional-core.md)|
|data shapes 驱动结构 - ETL、API、batch、typed records|[data-oriented.md](./data-oriented.md)|
|producer 与 consumer 解耦、hooks、signals、message queues|[event-driven.md](./event-driven.md)|
|有限的命名 states、命名 events、非法 transitions 很重要|[state-machine.md](./state-machine.md)|
|谁创建谁关闭 - files、locks、connections、pools|[resource-lifecycle.md](./resource-lifecycle.md)|
|concurrent I/O、task groups、cancellation、backpressure|[async-concurrency.md](./async-concurrency.md)|

Design principles（DRY、SOLID、KISS 等）位于 `../design-principles/` 下，命名的 structural patterns（Factory、Strategy、Observer）位于 `../design-patterns/` 下。这个目录关注的是底层执行模型，以及 state、decisions 和 side effects 应该放在哪里，而不是具体的命名结构。

这些 paradigms 并不是互斥的。一个现实中的服务会组合使用 imperative shell、functional 或 data-oriented core、用于生命周期的 state machine、声明式 config，以及用于 I/O 的 structured async。读对 paradigm 的关键，就是把系统的每一部分匹配到那个最容易推理的模型上。
