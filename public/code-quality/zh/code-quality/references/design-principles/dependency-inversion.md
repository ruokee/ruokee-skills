# Dependency Inversion and Dependency Injection

这两个概念相关但不同，经常被混淆：

- **Dependency Inversion Principle（DIP）：** 高层 policy 不应依赖低层 detail；二者都应依赖 abstraction。这个 abstraction 由高层代码需要什么来定义，而不是由低层代码碰巧提供什么来定义。
- **Dependency Injection（DI）：** 一种技术，让对象或函数从外部接收它的 dependencies，而不是自己构造或查找它们。DI 是实现 DIP 的一种方式，也是提升可测试性和边界隔离的主要杠杆。

DIP 是设计目标；DI 是机制。你可以不靠复杂框架就遵循 DIP，也可以在完全没有 “DI container” 的情况下使用 DI。

## 高层模块依赖 abstraction

DIP 要解决的问题是：业务规则如果直接调用数据库 driver、HTTP client、系统时钟或 `random`，就被这些细节焊死了。policy 就不能在不拖着 infrastructure 的情况下被阅读、测试或复用，而且低层 detail 的变化会向上扩散到高层规则。

反转依赖意味着高层代码把自己的需求表述为一个 abstraction——“我需要一个能告诉我当前时间的东西”、“我需要一个能保存 order 的地方”——而具体实现去满足这个需求。关键是，这个 abstraction 属于高层一侧。它由 policy 的需求塑造，而不是由低层 library 的完整 surface 决定。这和 [Interface Segregation](./solid.md) 的直觉一致：把 seam 保持得窄一些。

## Python 的做法

Python 很少需要其他生态里因 DIP 而发展出来的那套重型装置。轻量工具通常就够了：

- **Constructor 和 function 参数。** 把 collaborator 传进去。`def process(orders, repository, clock):` 不用任何仪式就反转了三个依赖。
- **`typing.Protocol`.** 结构化地定义 policy 所需的窄能力；只要对象有正确的方法就算满足，不必继承任何东西。见 [composition-over-inheritance](./composition-over-inheritance.md)。
- **普通 callable。** 当 dependency 是“我调用一下就能拿到值的东西”——比如 clock、ID generator、notifier——函数或 `Callable` 比 interface object 更轻。
- **为常见情况提供默认参数。** `def fetch(url, client=httpx.get):` 让真实默认值保持方便，同时也为测试留出传 fake 的 seam。

把具体 wiring 统一放在一个地方——`main()`、web app 的 startup、framework entry point。这个 _composition root_ 是高层 policy 与具体 detail 会合的地方；其他地方都依赖 abstraction。

## 什么时候 DI container 值得用，什么时候是过度设计

DI container（一个根据配置或注解构建并装配 object graph 的 framework）解决的是大多数 Python 项目并不拥有的问题。Constructor injection 加一个小的 composition root 就能支撑很长时间。只有在 object graph 真正庞大且动态时，container 才物有所值——很多可互换实现、复杂的 lifecycle 和 scoping 需求、跨很多 module 的配置驱动 wiring。

对典型应用来说，显式 composition root 比 container 更容易阅读、调试和追踪。全局的 _service locator_（代码向里伸手去取 dependency 的 registry）比这两者都差：它把自己满足的 dependencies 隐藏起来，把 DI 的显式性重新变回隐式的全局耦合。应当优先传入 dependencies。

## 测试收益

DI 是让代码可测试的最干净路径。当一个函数把 clock、repository 和 HTTP client 作为参数时，测试可以直接传入 fake 或 stub——不需要 monkeypatch module 内部，也不需要去 patch 很深的 implementation。这样测试就与边界（abstraction）保持耦合，而不是与实现耦合，因此内部重构不会破坏测试。过度 mock 和过深的 `patch` 目标，通常说明 dependencies 原本就没有被注入；修好 seam，就修好了测试 smell。另见 [tdd](./tdd.md)。

## 什么时候不要反转

把每个 dependency 都反转本身也是一种过度设计。不要反转这些东西：

- **稳定的标准库依赖和 pure function。** 调用 `json.dumps` 或一个 pure helper 的代码，不需要把它包进 Protocol 里；这里没有可变实现，也没有需要伪造的东西。
- **永远不会变化、也不需要 test double 的东西。** 一个只有单一实现且没有测试 seam 的 abstraction，是 speculative 的（[YAGNI](./yagni.md)）。

应当反转不稳定、带副作用或可替换的边界——外部系统、时间、随机数、文件系统、网络。稳定的 core 保持直接即可。

## 在 Python 中

- 优先使用 constructor parameters、function parameters、default arguments、small Protocols 和 factory functions。
- 在单一 composition root 中装配具体 dependencies。
- 用 adapter 包装外部 client；让 core 依赖 Protocol 或 callable。
- 使用 context manager 管理 dependency lifecycle（连接、文件、锁），并把它们放在 domain logic 之外。
