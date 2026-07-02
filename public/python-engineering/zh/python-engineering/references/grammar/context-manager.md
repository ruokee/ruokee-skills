# Context Managers

context manager 将 setup 动作与 teardown 动作配对，并保证无论代码块如何退出，teardown 都会运行。`with` 语句（以及用于异步资源的 `async with`）是 Python 将资源生命周期绑定到词法作用域的方式。

## 解决什么问题

资源有生命周期：文件必须关闭、锁必须释放、事务必须提交或回滚、连接必须归还给连接池。用裸 `try`/`finally` 也能正确处理，但冗长且容易出错 - 清理代码会偏离获取代码，嵌套资源则会产生层级很深、脆弱的块。

```python
with open(path) as handle:
    process(handle)
# handle is closed here, even if process() raised
```

`with` 块让生命周期可见：顶部是获取，主体是作用域，末尾是保证释放。关于 _谁拥有资源以及何时释放_ 的一般设计问题，见 [resource lifecycle design](../../../code-quality/references/programming-paradigms/resource-lifecycle.md)；本文只讨论语言机制。

## 协议

任何实现了两个方法的对象都可以是 context manager：

- `__enter__(self)` 在进入时运行。它的返回值会绑定到 `as` 目标。它常常返回 `self`，但也可以返回任意句柄（文件、cursor、connection）。
- `__exit__(self, exc_type, exc, tb)` 在退出时运行，始终会执行。正常退出时这三个参数为 `None`，否则描述当前传播中的异常。

```python
class Transaction:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def __enter__(self) -> Connection:
        self._conn.begin()
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        return False
```

## `__exit__` 中的异常处理

`__exit__` 的返回值是一个控制流决策，也是这个协议里最容易被误解的部分。返回 falsy 值（包括 `None`）会让正在传播的异常按正常方式继续冒泡。返回 truthy 值会 _抑制_ 异常，就像它从未发生过一样。

静默抑制异常几乎总是 bug。上面的事务会返回 `False`，因此失败的块仍然会抛出 - 它会回滚 _并且_ 继续传播。只有在吞掉异常正是 manager 的明确目的时才返回 `True`（即便如此，出于清晰性也更推荐使用 [`contextlib.suppress`](../stdlib/contextlib.md)）。一个负责清理的 manager 不应该同时隐藏触发清理的失败。

## 基于生成器的 context manager

对于不需要 class 的常见情况，`@contextlib.contextmanager` 可以把 generator 变成 context manager。`yield` 之前的代码是 setup，yield 出来的值成为 `as` 目标，`yield` 之后的代码是 teardown：

```python
from contextlib import contextmanager

@contextmanager
def timed(label: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        log.info("%s took %.3fs", label, time.perf_counter() - start)
```

`try`/`finally` 是关键：如果没有它，body 中的异常会跳过 teardown，因为异常是在 `yield` _处_ 重新抛出的。这个以及其他 `contextlib` helpers 的细节见 [contextlib reference](../stdlib/contextlib.md)。

## 异步资源

异步资源 - connections、sessions、在 setup 或 teardown 中必须 `await` 的 pools - 实现 `__aenter__` 和 `__aexit__`，并与 `async with` 一起使用：

```python
async with pool.acquire() as conn:
    await conn.execute(query)
```

它们的语义与同步协议类似，但进入和退出都可以挂起。只要 release 涉及 IO，就应使用 `async with`；当有 async manager 可用时，不要在 `async` 函数里直接调用阻塞式 close。生成器 helper 的异步对应物是 `@contextlib.asynccontextmanager`。

## 嵌套上下文

多个资源可以在一条语句里管理。带括号的形式（Python 3.10+）让长列表更易读，也便于生成干净的 diff：

```python
with (
    open(src) as fin,
    open(dst, "w") as fout,
):
    fout.write(transform(fin.read()))
```

manager 按从左到右进入、从右到左退出，因此依赖前一个资源的对象会先被释放。当资源 _集合_ 在运行时才知道时 - 变量数量的文件、动态构建的 manager 栈 - 应使用 [`contextlib.ExitStack`](../stdlib/contextlib.md) 而不是嵌套语句。

## 何时自己编写

当确实存在与你自己的资源或不变量绑定的 acquire/release 对时，编写自定义 context manager：领域锁、必须恢复的临时状态变化、类似事务的边界、metrics 或 tracing span。简单线性的 setup/teardown 优先使用 `@contextmanager`；当 manager 需要命名状态、作为对象复用，或需要被检查时，则优先使用 class。

如果 stdlib helper 已经能胜任，就不要自己写。`suppress`、`redirect_stdout`、`closing` 和 `nullcontext` 已经覆盖了很多常见需求，对于一次性的本地清理，用一个简单的 `try`/`finally` 也完全可以。为了只有三行的 `try`/`finally` 去写一个自定义 class，只会增加间接层而没有收益。
