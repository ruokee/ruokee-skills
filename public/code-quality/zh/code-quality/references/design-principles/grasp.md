# GRASP — General Responsibility Assignment Software Patterns

## 它是什么

GRASP 是九条启发式的词汇，用来回答最常见的设计问题：_责任应该放在哪里？_ 这个行为该由谁来做，这个对象该谁创建，这个 use case 由谁协调，我们要把规则放在哪里才能让变更被局部化。与 GoF 模式不同，GRASP 模式不是你要搭建的结构，而是分配责任时的推理工具。它们与 SOLID（见 [solid.md](./solid.md)）以及 [tell-dont-ask.md](./tell-dont-ask.md) 很自然地配合。

最常见的误用，是把 GRASP 当成 UML 驱动的流程，或者把 “Controller” 理解成“web controller”，然后把业务逻辑堆进 request handler 里。用得好时，GRASP 只是一个更精确的责任放置语言。

## 九个模式

**Information Expert.** 将责任分配给掌握完成这项责任所需信息的 class 或 module。行为应当倾向于它所操作的数据。这是 [tell-dont-ask.md](./tell-dont-ask.md) 的发动机，也是修复 “feature envy” smell 的解药——即某个 function 伸得太深去读别的对象的字段来做决定。

**Creator.** 将创建对象 B 的责任分配给聚合、包含、紧密使用 B，或持有 B 初始化所需数据的 class A。把构造放在已有构造知识的地方，可以减少耦合。当创建逻辑复杂到开始变化时，这就是 Factory 变得合理的地方。

**Controller.** 将处理一个系统操作（一个 use case）的责任分配给一个协调对象，这个对象既不是 UI，也不是 domain logic 本身。controller 的工作只是薄协调——接收请求、委托给 domain、返回结果。在 Python 里，CLI command handler 或 API view 应当是这样的 thin controller，而业务规则应留在 core module 中。

**Low Coupling.** 让模块之间的依赖尽量少。耦合越低，一个地方的变更传播到其他地方就越少，单元也越容易单独测试和复用。它是需要权衡的力量，不是绝对目标——必要的耦合仍然存在。

**High Cohesion.** 让每个 module 的内容彼此高度相关、聚焦明确。高内聚是 [solid.md](./solid.md) 中 SRP 的正向表达——它让 module 更容易理解，并拥有单一清晰的变更原因。低耦合和高内聚应当一起看；只优化其中一个而忽略另一个，设计就会变差。

**Polymorphism.** 当行为按 type 变化时，应用 polymorphism（在 Python 中可以是 duck typing、基于 `Protocol` 的 dispatch、dispatch map，或 `functools.singledispatch`），而不是到处写 `if/elif` 类型检查。这样每个变体都被局部化，新增一个变体变成“加一个”而不是“改很多”——这就是 OCP 背后的机制。

**Pure Fabrication.** 当没有任何 domain concept 适合承载某个责任时，就人为创造一个非领域对象来承载它——service、mapper、adapter、repository 或 policy function。这样可以保持 domain object 的内聚性，避免为了迎合 Information Expert 而把 infrastructure 关注点硬塞进去。Pure Fabrication 合理且常见；需要注意的是不要把它们当作无所不装的垃圾场。

**Indirection.** 将责任分配给一个中间对象或函数，以解耦两个原本会直接耦合的单元（例如 core 和第三方 client 之间的 adapter）。Indirection 是 Low Coupling 的工具，但每多一层，就多一个追踪跳点——只有在耦合问题真实存在时才加，而不要条件反射地加。

**Protected Variations.** 将预期的不稳定点包在一个稳定 interface 后面，使一侧的 variation 不会传递到另一侧。这是 OCP、DIP、Indirection 和 Polymorphism 的统一思想。关键字是 _predicted_——只保护那些真实、已识别的 variation，而不是任何“也许哪天会变”的点，否则就会滑向 [yagni.md](./yagni.md) 所警惕的 speculative generality。

## 在 Python 中

行为应尽量靠近拥有数据的地方（Information Expert）。CLI 和 API handler 保持为 thin Controller，规则放在 core。service、adapter、mapper 和 policy function 都属于合理的 Pure Fabrication。一旦 variation point 真实识别出来，就可以用 `Protocol`、adapter 或 deep module 来实现 Protected Variations（见 [deep-modules.md](./deep-modules.md)）。始终在 Low Coupling 与 High Cohesion 之间取得平衡，而不是单独最大化其中任何一个。
