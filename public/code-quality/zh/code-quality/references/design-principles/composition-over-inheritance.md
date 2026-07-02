# Composition over Inheritance

优先通过把更小的部分组装起来来组织行为——对象、函数、委托——而不是通过从 base class 继承实现。这里的建议是“优先”，不是“禁止”：inheritance 也有真正的用途，但它常常被过度使用为默认的复用机制，而 composition 通常是更灵活、耦合更低的选择。

## 为什么 inheritance 会带来耦合

Class inheritance 把两件在逻辑上独立的东西捆绑到一起：_实现复用_（subclass 得到 base class 的代码）和 _subtype substitutability_（subclass 的实例应当能在需要 base type 的地方工作，参见 [Liskov substitution](./solid.md)）。当你只是为了复用代码而继承时，你也同时继承了遵守 base contract 的义务，以及 base class 每一次变化都会带来的暴露面。

这会产生 _fragile base class_ 问题：base class 的修改可能以很难看出的方式破坏 subclass，因为 subclass 依赖的是 base class 的内部行为，而不只是它的公共接口。深层级的 hierarchy 会放大这个问题——行为分散在多层之中，要理解一个类就得读它所有祖先。

Composition 耦合更松。持有某个 collaborator 的对象只依赖这个 collaborator 的接口，并且可以在不改变自身 type 的情况下切换 collaborator。由 composition 组成的设计，变更半径更小，也更局部。

## 什么时候 inheritance 是合适的

- **真正的 is-a，且 contract 稳定。** 当 subtype 确实是 base 的一种 specialization，并且能够遵守 base 的每一项承诺（Liskov）时，inheritance 能忠实地建模这种关系。异常层次是一个干净的例子：`class TimeoutError(NetworkError)` 表达了 `except` 子句会用到的真实分类。
- **框架扩展点。** 许多框架就是设计成通过 subclassing 提供扩展（例如 Django view、`unittest.TestCase`）。在这里 inheritance 是框架指定的 hook，违背它反而徒增阻力。
- **小而稳定的抽象接口。** 继承一个定义了狭窄 contract（并且几乎不包含实现）的 abstract base，更接近接口实现，而不是实现继承，耦合也更低。

共同点是：当你想要 substitutability 且 contract 稳定时再继承，而不是为了只是复用几个方法。

## Python 的 mixin 文化及其风险

Python 支持 multiple inheritance，mixin 也是常见习惯：小的 class 给 host class 增加一段行为。用得好时——小、无状态、命名清晰、仅依赖 host 已文档化的接口——它们是合理的。用得不好时则会出大问题：

- **隐式状态和初始化顺序。** 一个 mixin 如果设置 attributes 或要求以某种特定顺序调用 `super().__init__()`，它就会在无形中与 host 以及其他 mixin 耦合。method resolution order（MRO）决定执行顺序，而多 mixin class 很难推理。
- **命名冲突。** 多个 mixin 定义或期望相同的 attribute 或 method 名称时，会通过 MRO 产生微妙交互。

让 mixin 保持小、无状态，并且名字要说明它们增加了什么。如果一个 mixin 需要大量状态或特定的 init 顺序，那就是该改用 composition 的信号。

## Protocol 作为 ABC inheritance 的替代方案

当目标是“这个对象必须支持这些方法”时，Python 的 `typing.Protocol` 可以让你用结构化方式表达，而不必建立 inheritance 关系。一个 class 只要有正确的方法就满足 Protocol，不必继承它。这带来了接口的 type-checking 价值，以及 [Interface Segregation](./solid.md) 的窄、由调用方定义的 contract 优势，同时没有共享 base class 带来的耦合。只有在你只是描述一种能力，而不是共享实现时，优先使用 Protocol 而不是 abstract base class inheritance。另见 [dependency-inversion](./dependency-inversion.md)。

## 常见错误

- **彻底禁止 inheritance。** 当框架预期的是 subclassing，或者确实存在稳定的 is-a 关系时，强行用 composition 只会增加样板代码并违背工具本身的使用方式。
- **透传样板代码。** composition 可能退化成一个对象把十几个方法逐一转发给持有的 collaborator。如果几乎每个方法都只是“一行委托”，就该重新考虑：也许这个 wrapper 之所以存在，是为了收窄或适配接口；也许 caller 应该直接持有这个 collaborator。
- **假装 subtype 只是为了复用。** 为了拿几个 helper method 而 inheritance，然后把其他方法 override 成 no-op 或 `NotImplementedError`，违反了 Liskov，这正是 composition（或者普通 helper function）才是正确工具的经典信号。

## 在 Python 中

- 默认用 functions、constructor parameters、Protocols、strategy objects 和 delegation 来做复用与变化。
- 只有在 exception hierarchy、framework hooks、真正稳定的 abstractions，以及少数清晰的小 mixin 场景下才保留 inheritance。
- 对共享代码，优先使用 module-level helper function 或 composition 出来的 collaborator，而不是一个仅仅为了放共享 method 的 base class。
