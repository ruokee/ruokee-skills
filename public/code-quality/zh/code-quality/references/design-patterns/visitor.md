# Visitor

Visitor 模式把操作与其作用的对象结构分离开。它允许你在一个固定的 node type 集合之上定义新操作，而无需修改这些类型。每个 node type 都实现一个 `accept(visitor)` 方法，调用 visitor 对应的 `visit_*` 方法，从而实现 double dispatch。

当类型集合稳定而操作集合经常变化时，这个模式最有价值。它把常见权衡反转了：新增一个操作很容易（增加一个新的 Visitor class），但新增一个 node type 则需要更新所有现有 Visitors。

## 结构

- Element（node type）：声明 `accept(visitor)`。
- ConcreteElement：通过调用 `visitor.visit_concrete_element(self)` 来实现 `accept`。
- Visitor（接口）：为每个 element type 声明一个 `visit_*` 方法。
- ConcreteVisitor：为每个 `visit_*` 实现操作专属逻辑。

## 何时适合这个模式

- node type 层次结构稳定。新增类型很少。
- 在这个结构之上的新操作很常见。
- 这些操作需要在不使用 `isinstance` 级联的情况下访问具体类型。
- 操作逻辑不应污染数据 class。
- 存在多个独立的遍历关注点（lint、transform、serialize、pretty-print）。

## 何时不适合这个模式

- node type 经常变化。每新增一种类型，都要更新所有 Visitors。
- 结构足够简单，一个递归函数或 `match`/`case` 就能搞定。
- 只有一两个操作。`accept` / `visit` 的仪式感并不会增加清晰度。
- 语言支持 [pattern matching](../../../python-engineering/references/grammar/match-case.md) 或 [`singledispatch`](../../../python-engineering/references/stdlib/functools.md)，双重分发就显得多余。
- 操作并不需要完整的具体类型 - 一个通用接口方法就够了。

## Python 替代方案

Python 提供了比经典 Visitor 更轻量的替代方案：

- **`match`/`case` 加结构模式**：适用于 tagged union、dataclass 层次或 typed dict。不需要 `accept` 方法。见 [pattern matching reference](../../../python-engineering/references/grammar/match-case.md)。
- **`functools.singledispatch`**：按第一个参数的类型分发。适合在封闭类型集合上做单参数操作。见 [functools](../../../python-engineering/references/stdlib/functools.md)。
- **字典分发**：把 type 映射到 handler function。最简单的形式；没有基础设施。
- **在 node 上放方法**：如果操作很少且稳定，就把行为直接放到 node 上。不需要这个模式。

经典的 accept/visit 双重分发 Visitor，最适合的场景是：你希望用一个 protocol 强制每个 visitor 都处理每种类型；你需要在 traversal 过程中由 visitor object 累积状态；或者类型层次存在于你无法控制的 library 中。

## 常见实现问题

**遍历责任。** 谁来走树 - visitor、node 的 accept method，还是外部 iterator？在一个结构内部保持一致。混用不同策略会导致 node 被访问两次或漏访问。

**返回值。** 经典 Visitor 使用无返回值的 visit，通过累积状态来工作。对于每次访问都产生值的函数式遍历，可以考虑让 visit method 返回值，而不是修改 visitor 自身。

**默认处理。** 提供一个 `visit_default` 或 `generic_visit` 来处理未知 node type。否则，新增 node type 时可能会静默跳过访问，而不是抛错。这在不断演化的树结构中尤其重要。

**Composite children.** 对于树结构，要决定 `accept` 是否自动递归子节点，还是必须由 visitor logic 显式递归。自动递归很方便，但会隐藏遍历顺序；显式遍历则让 visitor 控制深度优先还是广度优先，并允许剪枝。

## 与 Strategy 的关系

[Strategy](strategy.md) 变的是一个稳定调用点背后的算法。Visitor 变的是一个稳定类型层次结构之上的操作。Strategy 是按调用点变化；Visitor 是按 node type family 变化。如果你是在多个类型上做一个操作，Visitor 可能过度设计 - [Strategy](strategy.md) 或普通函数就够了。
