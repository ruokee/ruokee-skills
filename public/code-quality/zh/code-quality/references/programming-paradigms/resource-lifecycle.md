# Resource Lifecycle Design

Resource 是任何需要被获取并随后释放的东西：file handle、socket、lock、database connection 或 transaction、temporary directory、thread 或 task、subprocess。Resource lifecycle design 要回答的是，对每一个 resource，谁创建它、谁关闭它，以及它如何在所有退出路径上被释放——包括 exception path。大多数 resource leak 和 “connection pool exhausted” 事件，本质上都是从未被显式回答过的 lifecycle 问题。

## Ownership

每个 resource 都需要一个且只有一个 owner：负责释放它的代码。Ownership 不清晰是 leak 和 use-after-close bug 的根源（所有人都以为会有人去关，但实际上没人关；或者某个持有者关掉了它，而另一个持有者还在使用）。

最清楚的规则是：创建 resource 的代码拥有它并负责关闭它，而且要在自己控制的 scope 中完成。若某个 function 只在自己的执行期间需要 resource，它就应当在本地创建、使用并释放它。若 resource 必须活得比单个 function 更久，那么 ownership 就要上移到更长生命周期的持有者——application object、context、pool——而那个持有者的 lifecycle 就变成了 resource 的 lifecycle。把一个打开的 resource 传给不拥有它的 function 是可以的，只要约定清楚：callee 使用它，caller 关闭它。

Function signature 可以把 ownership 显式化。接受一个已经打开的 resource 的 function 是在借用它；自己打开 resource 的 function 是在拥有它。把两者混在一起——有时自己打开，有时又接受外部传入——就会让 ownership 变得模糊，resource 也更容易泄漏。

```python
def write_report(out: TextIO, rows: list[Row]) -> None:
    # borrows out: the caller opened it and the caller closes it
    for row in rows:
        out.write(format_row(row))


def save_report(path: str, rows: list[Row]) -> None:
    # owns the file: opens it, uses it, releases it, all in one scope
    with open(path, "w") as out:
        write_report(out, rows)
```

借用的 function 永远不应该调用 `out.close()`——那会释放一个它并不拥有的 resource，并让调用者感到意外。在 interface 中始终保持 borrow-versus-own 的一致性，才能让 leak 更容易推理。

## RAII 和 context managers

RAII（Resource Acquisition Is Initialization）把释放绑定到 scope 结束，而不是绑定到一个你可能忘记调用的手工清理函数。Python 通过 context manager protocol 和 `with` / `async with` 来表达这一点：resource 在进入时被获取，在退出时被释放，无论 block 是正常返回还是抛出异常。

```python
with open(path) as f:
    data = f.read()
# f is closed here, even if read() raised
```

不要依赖 `__del__` 或 CPython 的 reference counting 来释放 files、locks、transactions 或 connections。destructor 的触发时机在不同实现之间会变化，在 reference cycle 下也会失效，而且在 exception path 上不可靠。要把释放显式化，并让它与 scope 绑定。

## 固定范围与动态资源集合

对于一组固定、静态已知的 resources，嵌套的 `with` 语句（或一个带多个 managers 的单个 `with`）是最清楚的表达方式。当 resource 的 _数量_ 是动态的——比如针对每个输入路径打开一个 file，或者获取一组可变数量的 connections——就应使用 `contextlib.ExitStack`（或 `AsyncExitStack`），而不是手写一个嵌套的 cleanup 栈：

```python
from contextlib import ExitStack


def read_all(paths: list[str]) -> list[str]:
    with ExitStack() as stack:
        files = [stack.enter_context(open(p)) for p in paths]
        return [f.read() for f in files]
```

`ExitStack` 能保证每个已经进入的 resource 都按逆序释放，即使中途某个 acquisition 失败也一样。

## 异常路径

清理必须在出错时执行，而这恰恰是最容易被遗漏的时候。优先使用 `with`，而不是手写 `try/finally`，因为 manager 会把清理一次性、正确地封装起来。如果你确实要写 `try/finally`，释放逻辑应放在 `finally` 中，而不是 `try` 之后。自定义 context manager 的 `__exit__` 不应吞掉异常，除非“抑制异常”正是其明确且有文档说明的目的——如果 `__exit__` 返回 truthy，错误会被悄悄隐藏。

## Async 资源 ownership

Async resources（connections、sessions、async generators）遵循同样的 ownership 规则，只是使用 `async with` 和 `__aenter__` / `__aexit__`。另外有两个额外风险：持有 resource 的 async generator 可能会被挂起并永远不再恢复，因此要使用 `contextlib.aclosing()` 来保证清理会执行；而被 task 拥有的 resource 只有在该 task 被正确 `await` 或取消时才会释放，因此 background tasks 需要显式的 lifecycle management（见 [async-concurrency.md](./async-concurrency.md)）。

## Application 启动与关闭

那些生命周期最长的 resources——connection pools、clients、thread pools、caches——由 application 自身拥有。应在 startup 时获取它们，在 shutdown 时按相反顺序释放它们。Framework 的 lifespan hooks（ASGI lifespan、app factories、dependency-injection scopes）才是合适的位置。避免在 import 时就获取这些资源：import-time side effects 会让 modules 在测试或工具场景下变得不安全，也会把 resource lifecycle 绑到 import 顺序上，而不是 application lifecycle 上（关于 entry-point structure，见 [imperative.md](./imperative.md)）。

## 部分初始化与释放顺序

有一种微妙的失败模式会在多个资源按顺序获取、而后面的某一步失败时出现。之前已经打开的资源必须仍然被释放，而且要按逆序释放，尽管 setup 从未真正完成。手写代码往往在这里出错——“只完成了一半” 的 cleanup 路径，通常是最不容易被测试到的路径。

这也是为什么更推荐用 `with` 和 `ExitStack`，而不是手写 setup：它们会只释放那些已经成功进入的资源，并按逆序释放，不管 setup 在哪里失败。按依赖顺序获取（先 connection，再运行其上的 transaction），自动的逆序释放就会正确拆除：先 transaction，再 connection。当你必须显式决定释放顺序时，规则就是后获取的先释放，因为后来的资源在自己的清理过程中可能仍依赖更早的资源保持存活。

## Pooling 和 lease 模式

当 acquisition 成本很高（database connections、HTTP sessions）时，pool 会拥有一组长期资源，并在一个工作单元期间把它们 _lease_ 给调用者。调用者获取和释放的不是 resource 本身，而是 lease——通常通过一个 context manager，在进入时从 pool 中取出资源，在退出时归还。纪律是一样的：被 lease 的 resource 有清晰的 scope，并且在所有退出路径上都返回 pool，包括异常路径。泄漏一个 lease 比泄漏一个 file 更糟，因为它会永久缩小 pool，直到耗尽。

```python
def handle_request() -> Result:
    with pool.connection() as conn:   # lease on entry, return on exit
        return run_query(conn)
```

同样的 RAII 纪律可以从单个 file handle 扩展到整个 application 级的 pool：命名 scope，让释放自动完成，永远不要依赖 garbage collector 替你做这件事。
