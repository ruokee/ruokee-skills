# Domain-Driven Design Essentials

Domain-Driven Design（DDD）是一种围绕领域本身的语言和边界来建模复杂业务领域的方法，而不是围绕数据库表或框架文件夹来建模。本文覆盖最能改善代码组织和命名的概念。它不能替代完整的 DDD 文献，而且大多数项目只需要其中一部分。

核心前提是：在真正复杂的业务软件中，难点不是技术，而是领域——它的词汇、规则、不变量，以及子领域之间的边界。与这些概念相映射的代码，更容易讨论、修改并保持正确。

## Ubiquitous language

一套在领域专家、代码、测试和讨论中一致使用的共享词汇。如果业务说的是 “settlement”，那么类就该叫 `Settlement`，而不是 `PaymentRecord`。其收益是减少翻译成本：会议里用的词和代码里的词一致时，误解更不容易滑到生产环境。这是 DDD 中最具可移植性的一部分——即使是小项目，也能从按领域语言命名中获益。

## Bounded contexts

bounded context 是一个边界，在这个边界内模型和语言保持一致。同一个词在不同 context 里可以有不同含义：“Customer” 在 billing 中是一个带有付款条款的 account，在 support 中则是一个有工单历史的人。强行把它们塞进一个共享模型，只会制造两边都不顺手的缠结。bounded context 让每个子领域保持自己的连贯模型，并在 seam 处显式翻译。这与 [Single Responsibility](./solid.md) 一致：一个 context 只有一个变更来源，因为它只对业务中的一部分负责。

## Entities 和 value objects

用 identity 区分的两类 domain data：

- **Entity.** 具有在属性变化后仍然延续的独立 identity。`User` 即使修改了 name 和 email，仍然是同一个 user；决定 equality 的是 identity，而不是字段值。Entity 有 lifecycle。
- **Value object.** 完全由其属性定义，没有自身 identity。`Money`、`DateRange`、`Address`——两个字段相同的 value object 可以互换。Value object 天然适合 immutability，这会消除大量 aliasing bug。

把某样东西建模为 value object，而不是裸 primitive，是 DDD 里收益最高的动作之一。用 `Money` value object 替换 `dict[str, Any]` 或松散的 `(amount, currency)` tuple，可以修复 [primitive obsession](../refactoring/index.md)，并给 invariants 找到落点。

## Aggregates

aggregate 是一组 entities 和 value objects，被当作一个整体来变更，其中一个 entity 是 **aggregate root**。外部代码只引用 root；root 负责强制执行跨整个 cluster 的 invariants，并作为 transaction boundary。例如，`Order` aggregate 拥有它的 `LineItem`s；你不会直接修改某个 line item，而是通过 order 进行，这样 order 就能强制诸如“总额不能超过 credit limit”之类的规则。aggregate 是 [Tell, Don't Ask](./tell-dont-ask.md) 和 [Information Expert](./grasp.md) 启发式真正落地的地方——规则和它所治理的数据待在一起。

## Domain events

domain event 记录领域中发生了有意义的事情——`OrderPlaced`、`PaymentReceived`。事件让副作用和跨 context 的响应变得显式且解耦：order context 发布 `OrderPlaced`，而不需要知道 shipping 和 analytics 都在监听。只有当响应确实跨边界时才使用它们；不要为了用而把每一次状态变化都变成事件。

## Anti-corruption layer

当与外部系统或 legacy model 集成，而它们的概念与你的不一致时，anti-corruption layer（ACL）负责在两者之间翻译，避免 foreign model 渗入你的 clean domain。它是 [Adapter](../design-patterns/adapter.md) 模式在领域层面的应用：ACL 在内部说你的 ubiquitous language，在外部说外部系统的语言。这样可以保护 core model 不被外部命名和结构污染。

## 什么时候不要应用 DDD

DDD 的完整机制——aggregate、repository、domain service、unit of work——成本很高，只有在真正的领域复杂度下才值得。把它用在简单 CRUD、脚本或小工具上，就是过度设计（[YAGNI](./yagni.md)）。常见的两种失败模式：

- **Folder cosplay.** 创建 `domain/`、`application/`、`infrastructure/` 目录，并不能让设计变得 domain-driven；它只是在别处搬运同样的逻辑。
- **Anemic model.** Entity 只是裸字段袋，所有规则都放在 service class 里。这与 DDD 的初衷相反，也放弃了它最主要的收益。

## 在 Python 中

- 小项目可以只借用 ubiquitous language、value object 和 invariant 思维，而不必采用完整的分层架构。
- Value object 很适合映射到 `dataclass(frozen=True)`、`attrs`、Pydantic model 或普通 class。
- Entity 不一定就是 ORM class。当持久化关注点扭曲了模型时，应将 domain model 与 persistence model 分开。
- 只有在你确实需要 transaction boundary、存储的 test double，或与 ORM 隔离时，才引入 repository 和 unit of work，而不是默认就上。
