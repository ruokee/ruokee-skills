# Law of Demeter

Law of Demeter（LoD），也叫最少知识原则，说的是一个单元应该只和它的直接朋友交谈，避免穿过一个对象去操作它返回的对象。一个 method 应该只和以下对象交互：它自己的对象、作为参数传入的对象、它自己创建的对象，以及它的直接组件。它不应该沿着一长串中间对象导航，去接触一个远处的目标。

重点不是表达式里有多少个点。重点是调用方被迫知道了多少自己并不拥有的对象内部结构。当调用方一路写着 `a.b.c.d` 时，它硬编码了三层结构知识，而这层结构的任何变化都会扩散到所有走过同一路径的 caller。

## 它解决什么问题

结构耦合。代码穿透对象时，不只是依赖了直接 collaborator，还依赖了该 collaborator 暴露出来的整张形状图。图中深处的一处变化——字段重命名、插入中间对象、类型改变——都会传播到远处、看起来无关的调用点。这就是 shotgun surgery 的经典症状：一个小小的结构变更迫使很多地方修改。

LoD 会推动你给直接 collaborator 提供一个表达“你想要什么”的 method，于是 collaborator（真正拥有结构的一方）自己决定“怎么拿到它”。结构知识留在结构所在的地方。

## 火车事故式调用链

“train wreck” 是一串连在一起的 accessor 链，看起来像车厢一节接一节：

```python
zip_code = order.customer.address.zip_code        # train wreck
tax_rule = order.customer.account.region.tax_rule # train wreck
```

这段代码现在知道：order 有 customer，customer 有 address，address 有 zip code。若以后 `Address` 被拆开，或者 `Customer` 多了一层间接，所有这类链都会断。修复方式是用领域术语向最近的对象提问：

```python
zip_code = order.shipping_zip_code()
needs_review = order.requires_tax_review()
```

现在是 order 自己负责遍历。调用方表达意图；结构被隐藏起来。这与 [Tell, Don't Ask](./tell-dont-ask.md) 直接相关：与其跨好几跳把数据取出来再在外部做决定，不如让数据所有者提供一个回答问题的 method。

## 什么时候它重要

- 领域对象上，链式访问会驱动业务规则
  （例如 `order.customer.address.zip_code` 决定税务行为）。
- 调用方穿过 repository、client 或 response object，深入其内部结构，从而与内部布局耦合。
- 测试需要 monkeypatch 到对象图深处——深 mock 往往意味着被测代码对远处结构知道得太多。

在这些情形里，结构变化的 blast radius 很大，LoD 就是用来帮助你找到该在哪里加 semantic method 的好视角。

## 什么时候它过于严格

如果把 LoD 机械地理解为“数点，然后禁止”，它就会变成噪音。

- **Fluent interfaces 和 builders。** `query.filter(...).order_by(...).limit(10)` 是设计出来的链式调用。每次调用返回的仍是同一个概念对象，而不是更深一层的内部对象。
- **Data traversal libraries.** Pandas、SQLAlchemy queries 和 `pathlib.Path` 的链式写法是惯用法。`path.parent.parent / "config.toml"` 不是耦合问题。
- **透明的数据载体。** 从 DTO 或 JSON-like 结构里直接读 `response.json()["items"][0]["id"]`，只是普通数据访问，不是对行为性对象内部结构的结构耦合。纯粹作为数据承载的 dataclass 可以直接遍历。

判断标准始终是：_调用方是否因此知道了某种内部结构，而这个结构一变它就会坏？_ 如果链路经过的是稳定 interface 或透明数据，那就没有违规。如果链路编码的是拥有行为和 invariants 的对象的私有布局，那 LoD 就派上用场了。

## 以错误方式强行遵守

强行修这个问题有时比问题本身更糟。把每条链都包成一个 forwarding method，只会制造一堆无意义的 pass-through method（例如 `def zip_code(self): return self._address.zip_code`），它们既没有语义，只是把耦合往上一层搬。这就是 shallow wrapper——见 [deep modules](./deep-modules.md) 的讨论。只有当某个 method 真正表达了有意义的领域问题时，才引入它，而不是仅仅为了去掉一个点。

## 在 Python 中

- 看结构知识和变更传播，而不是只看点号数量。
- 给 domain object 提供语义化查询：`order.shipping_postal_code()`、`invoice.is_overdue()`，而不是暴露嵌套字段让 caller 去一层层走。
- 让 DTO、dataclass 和 JSON-like 数据保持可透明遍历。
- 把测试中的 deep mock 当作信号：如果测试必须 patch `a.b.c.d`，生产代码大概率对那条路径知道得太多。

## 相关原则

LoD 与 [information hiding](./deep-modules.md) 天然相配：二者都减少外部世界对内部结构的依赖，也都限制变更传播的距离。它还与 [Tell, Don't Ask](./tell-dont-ask.md) 以及 GRASP 的 [Information Expert](./grasp.md) 启发式重叠——三者都推动行为向持有所需数据的对象靠拢。
