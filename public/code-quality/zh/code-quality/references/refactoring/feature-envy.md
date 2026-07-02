# Feature Envy

## 它是什么

Feature Envy 指的是一个方法似乎对另一个对象比对自己所属的对象更感兴趣。它不断伸手去拿第二个对象的数据，取出好几份，再做本来应该由那个对象自己完成的计算。这个方法在“嫉妒”它所操作的类的特征。典型形状是：`A` 上的一个方法反复调用 `b.x`、`b.y`、`b.z` 并把它们组合起来，而几乎不碰 `A` 自己的状态。

这个 smell 之所以重要，是因为它把行为放错了地方。逻辑依赖的是另一个对象的内部结构，所以一旦那些内部结构变化，这个远处的方法也会坏掉 - 这种耦合本不该存在。与此同时，拥有数据的对象却变得贫血，只剩字段袋，属于它自己的操作却被放在别处。这与“行为应该和它需要的数据放在一起”的原则正相反（见 [../design-principles/tell-dont-ask.md](../design-principles/tell-dont-ask.md) 以及 GRASP 的 Information Expert，见 [../design-principles/grasp.md](../design-principles/grasp.md)）。

## 信号

看一个方法，数一数它碰的是谁的数据。如果它访问别的对象的字段和方法比访问自己的还多，那就是嫉妒。一个可靠的具体信号是：一串 `other.a`、`other.b`、`other.c` 被拿来做计算 - 尤其是那些来自 [../design-principles/law-of-demeter.md](../design-principles/law-of-demeter.md) 所说的 train-wreck chain，也就是调用方穿透了自己不该了解的结构。

```python
# Envious: the method lives on Order but is all about customer.address
class Order:
    def shipping_label(self) -> str:
        c = self.customer
        return f"{c.address.street}, {c.address.city} {c.address.postal_code}"
```

这里的计算完全是关于 address 的；它应该放在 `Address`（或者 `Customer`）上，而不是 `Order` 上。

## 怎么处理

通常的修法是 [move-function.md](./move-function.md)：把方法移到拥有它所嫉妒的数据的对象上。如果只有方法的一部分表现出嫉妒，可以先用 [extract-function.md](./extract-function.md) 把那部分隔离出来，然后再移动提取出的那一段。移动完成后，原来的调用点会让正确的对象去做这件事（`address.formatted()`），对内部结构的依赖也就消失了。

指导性问题是 Information Expert 那句：哪个对象持有这段逻辑所需的数据？把逻辑放到那里。这样通常会降低耦合、让对象更丰富，而且调用点会像在发出请求，而不是在审问对象。

## 什么时候它是可以接受的

Feature Envy 只是一个启发式规则，不是法律。下面这些合法模式看起来也像嫉妒，但应该保留：

- **工具函数和纯函数。** 一个函数的全部工作就是处理传入的数据 - 格式化器、序列化器、对值对象做计算的函数 - 本来就应该大量使用这些数据。把它们搬到数据类上并不总更好，尤其在函数式风格中，行为本来就常常以命名函数的形式存在，输入是数据。functional core 刻意把数据和操作数据的函数分开。
- **横切关注点。** 日志、指标、授权和 transaction handling 必然会触碰其他对象的数据，这是它们的本性，不是放错地方。
- **数据转换和映射。** mapper 从对象 `A` 读取数据并构建对象 `B`，不可避免地会访问 `A` 的很多字段。这正是 mapper 的作用；这不算嫉妒。
- **数据是透明记录。** 从一个没有不变量的 `dataclass` 或 DTO 里取字段完全没问题 - 没有行为被丢在那儿，因为这个记录本来就不是为了拥有行为。对于 read models 和 DTO 的 Tell-Don't-Ask 例外也适用于这里。
- **移动后会产生更糟的耦合。** 如果“拥有者”是一个稳定的第三方类型，或者你不想为了一个调用方把它膨胀起来的类，那么保留逻辑在原处可能更划算。

判断标准在于：行为是不是依赖另一个对象的 _内部结构_（那就移动），还是只是把它的公共数据当输入来消费（通常可以）。Primitive Obsession 往往会掩盖 envy：当行为嫉妒一个无法承载方法的 primitive 时，真正的修法通常是引入一个能承载行为的 value object - 见 [primitive-obsession.md](./primitive-obsession.md)。
