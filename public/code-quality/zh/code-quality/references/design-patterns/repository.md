# Repository

Repository 模式在持久化机制之上提供一个类似 collection 的接口，把领域逻辑与存储细节隔离开。它在领域模型和数据映射层之间充当中介，提供 `get`、`add`、`remove` 以及返回领域对象的查询方法。

它的核心价值在于：领域代码通过一个干净的接口操作领域对象，而不需要知道数据来自数据库、文件系统、API、缓存还是内存集合。这让领域逻辑可以在没有真实基础设施的情况下测试，也允许在不修改业务规则的前提下更换存储技术。

## 结构

- **Repository 接口**（Protocol 或 ABC）：定义类似 collection 的方法（`get_by_id`、`add`、`remove`、`list_by_criteria`）。
- **具体 Repository**：使用某种特定技术实现接口（SQLAlchemy session、原生 SQL、HTTP client、文件系统）。
- **领域对象**：Repository 返回的纯领域实体或聚合。
- **应用 / 服务层**：使用 Repository 接口，而不是具体实现。

依赖方向向内流动：领域代码依赖 Repository _接口_，而具体实现依赖它所持久化的领域对象。这是把 [dependency inversion](../design-principles/dependency-inversion.md) 应用到持久化上的结果。

## 何时适合这个模式

- 领域逻辑足够复杂，把它与持久化隔离会提升清晰度和可测试性。
- 可能存在多个存储后端，或者很可能会出现（生产数据库、测试内存存储、从一个 ORM 迁移到另一个）。
- 应用采用分层或 hexagonal architecture，并且边界清晰。
- 业务规则应该能在没有数据库 fixture 的情况下测试。
- 团队希望有一个一致、可发现的数据访问 API。

## 何时不适合这个模式

- 应用只是一个很薄的 CRUD 层，领域逻辑很少。给 ORM 再包一层 Repository 只会增加间接层，却没有减少复杂度。
- ORM 本身已经提供了足够干净的抽象（例如 Django 的 Manager/QuerySet，适用于简单应用）。
- 只会使用一种存储技术，而且领域逻辑很简单。
- 查询高度动态或偏分析型。Repository 接口会变成对复杂 SQL 的脆弱抽象 - 这种情况下，专门的 query service 或 CQRS 分离会更合适。
- 项目只是一个只有单一数据源的脚本或小工具。

## 常见实现问题

**接口膨胀。** Repository 如果长出几十个查询方法，就会失去抽象价值。应把接口聚焦在 [domain](../design-principles/ddd.md) 操作上，而不是做一个通用 query builder。

**脆弱抽象。** 暴露 ORM 特定概念的方法（session、flush、lazy loading、query builder）会直接破坏这个模式的初衷。应返回完整加载的领域对象。如果调用方需要分页、过滤或排序，应把它们设计成 Repository 参数，而不是让 ORM 的查询链条泄漏出来。

**transaction boundary。** Repository 通常不拥有 transaction。transaction boundary 属于应用 / 服务层，或者属于 [Unit of Work](unit-of-work.md)。在 Repository 内部提交会让跨多个聚合协调写入变得不可能。

**急加载与延迟加载。** 如果 ORM 延迟加载关联对象，那么在 Repository 边界之外访问它们可能会失败，或者触发意外查询。应在 Repository 边界决定加载策略，使返回的对象对于预期用例来说是完整的。

**测试。** 为领域逻辑的单元测试提供一个内存实现。集成测试仍然需要真实数据库 Repository 来验证查询、约束和迁移。

## 与 Unit of Work 的关系

Repository 通过类似 collection 的 API 处理单个聚合的持久化。[Unit of Work](unit-of-work.md) 处理跨多个 Repository 的事务一致性。它们是互补的：Repository 提供 collection 接口，Unit of Work 提供 commit/rollback 边界。它们一起让应用层同时掌控“要持久化什么”和“何时持久化”。

## 与 Facade 的关系

Repository 是面向领域的、作用在持久化子系统之上的 [Facade](facade.md)。区别在于意图：Facade 是为任何消费者简化复杂子系统；Repository 则专门在领域对象和存储之间充当中介。如果你的“repository”其实只是为了简化一个复杂外部 API，而并没有领域对象，那么 Facade 可能是更合适的名字。
