# Unit of Work

Unit of Work 模式维护一个受业务 transaction 影响的对象列表，并协调把变更一次性写入数据库。它跟踪哪些对象是新的、被修改的或被移除的，并把所有变更一起提交 - 如果任何一步失败，就全部回滚。

它的主要价值在于 transaction 一致性：必须一起成功或失败的多个 repository 操作，由 Unit of Work 协调，而不是各个 repository 各自独立提交。

## 结构

- **Unit of Work**（接口）：声明 `commit()`、`rollback()`，并提供对 repository 的访问。
- **具体 Unit of Work**：包装数据库 session/connection，跟踪变更，执行 commit/rollback。
- **Repository**：通过 Unit of Work 访问；在它的 transaction scope 内运行。
- **应用 / 服务层**：创建 Unit of Work，通过它的 repository 执行操作，然后 commit 或 rollback。

## 何时适合这个模式

- 一个业务操作会触及多个必须原子持久化的聚合。
- 应用有明确的服务层方法来编排领域逻辑。
- transaction boundary 需要在应用层清晰可见并且可测试。
- 多个 [repositories](repository.md) 共享同一个 session/connection，而且它们的写入必须协同。
- 架构受益于把“发生了什么变化”和“何时持久化”分开。

## 何时不适合这个模式

- 每次操作都只是单实体 CRUD，没有跨聚合一致性需求。ORM session 或一个简单的 `with db.transaction():` 块就足够了。
- 框架已经以声明式方式管理 transaction（例如简单场景下 Django 的 `@transaction.atomic`）。
- 应用偏读多写少，几乎不需要写入协调。
- 跨多个服务的分布式 transaction - Unit of Work 只适用于单个数据库边界；跨服务一致性需要 saga 模式或 eventual consistency。
- 显式跟踪变更的开销超过了简单应用中所带来的收益。

## 常见实现问题

**作用域。** Unit of Work 应当只活一个业务操作。把它放在应用启动时创建并在请求之间共享，会导致陈旧数据和并发 bug。在 web 应用中，作用域应当是一次请求；在 worker 中，作用域应当是一项 job。

**ORM 集成。** SQLAlchemy 之类的 ORM 内部已经实现了 Unit of Work - Session 会跟踪脏对象并在 commit 时 flush。把 ORM session 再包一层显式 Unit of Work class 的意义，是让边界在应用层更清楚、可测试，而不是重复实现变更跟踪。如果 ORM 自带的 session 管理已经足够显式，那么额外再包一层可能只是在增加仪式感，却没有价值。

**嵌套 transaction。** 应避免深度嵌套的 Unit of Work。如果子操作需要独立的 commit/rollback，请显式使用 savepoint，而不是嵌套 Unit of Work。

**错误处理。** 任何异常路径都必须 rollback。[Context managers](../../../python-engineering/references/grammar/context-manager.md)（`with uow:`）是最自然的方式 - `__exit__` 在存在异常时调用 rollback。这也正是 [resource lifecycle](../programming-paradigms/resource-lifecycle.md) 模式的工作方式：把 acquire 和 release 配对。

**测试。** Unit of Work 边界是天然的测试分界。使用 mock 或内存实现，可以让服务层测试在没有数据库的情况下验证编排行为。

## Python 实现形态

在 Python 中，Unit of Work 自然会表现为一个 context manager：

```python
with unit_of_work() as uow:
    order = uow.orders.get(order_id)
    order.confirm()
    uow.payments.add(payment)
    uow.commit()
```

如果在 `commit()` 之前发生异常，context manager 的 `__exit__` 会调用 `rollback()`。这让 transaction boundary 既显式又能在异常情况下保持安全。`context manager mechanism` [context manager mechanism](../../../python-engineering/references/grammar/context-manager.md) 保证即使出现意外异常也能完成 teardown。

## 与 Repository 的关系

[Repository](repository.md) 提供面向单个聚合的 collection-like API。Unit of Work 负责协调这些变更 _何时_ 被持久化。它们天然可以组合：Unit of Work 拥有或提供对 repository 的访问，而同一个 Unit of Work 内的所有 repository 操作共享它的 transaction scope。关于如何判断什么算一个聚合，也可以参考 [DDD aggregate boundaries](../design-principles/ddd.md)。
