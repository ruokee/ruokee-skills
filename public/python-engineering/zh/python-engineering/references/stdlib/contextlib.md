# contextlib

`contextlib` 提供了一些 helper，用于在不写完整 `__enter__` / `__exit__` class 的情况下构建和组合 context manager。它补充了 [`with` protocol](../grammar/context-manager.md)：grammar 文档说明协议是什么、何时使用；本文说明如何借助标准工具低成本地产出 context manager。

## `@contextmanager` 和 `@asynccontextmanager`

`@contextmanager` 会把 generator 变成 context manager。`yield` 之前的代码在进入时运行，yield 出来的值成为 `as` 目标，`yield` 之后的代码在退出时运行。要处理异常，应把 `yield` 包在 `try` / `finally` 中：

```python
from contextlib import contextmanager

@contextmanager
def acquired(resource):
    resource.open()
    try:
        yield resource
    finally:
        resource.close()
```

generator 必须恰好 `yield` 一次。`with` body 内抛出的异常会在 `yield` 位置被重新抛出，这就是为什么 cleanup 应该放在 `finally` 而不是裸 `yield` 之后。`@asynccontextmanager` 是对应的 coroutine 版本，由 `async with` 驱动，允许在 `yield` 周围使用 `await`。

对于顺序式 setup/teardown 逻辑，这种 decorator 形式应该作为默认选择。只有当你需要作为实例复用、需要多个方法，或需要重入性时，才考虑完整的 class。

## ExitStack 和 AsyncExitStack

`ExitStack` 管理一组 _动态_ 的 context manager - 当资源数量在 parse 时不知道，或者资源是在循环中获取时：

```python
from contextlib import ExitStack

with ExitStack() as stack:
    files = [stack.enter_context(open(p)) for p in paths]
    process(files)
# every file closes here, in reverse order, even if one raises
```

`enter_context` 会注册一个已经创建好的 context manager；`callback` 会注册一个任意 cleanup function；`push` 会注册一个 `__exit__` 风格的 callable。一个很有用的模式是部分初始化安全：先把资源构建到 stack 上，然后在构建完全成功后调用 `stack.pop_all()` 把所有权转移出去，这样中途失败仍会撤销到目前为止获得的一切。`AsyncExitStack` 是 `async with` 对应物，提供 `enter_async_context` 和异步 callback。

## suppress

`suppress(*exceptions)` 会忽略其块中抛出的指定异常 - 它清晰地替代了 `try/except SomeError: pass`：

```python
from contextlib import suppress

with suppress(FileNotFoundError):
    path.unlink()
```

保持 body 只包含你确实想忽略失败的那一个操作。把多个语句包进去，会让后面另一个同类型但不相关的失败悄悄漏掉。

## redirect_stdout 和 redirect_stderr

它们会在块的持续时间内临时把 `sys.stdout` / `sys.stderr` 重新绑定到任意类文件对象。它们适合捕获你无法控制的代码输出：

```python
import io
from contextlib import redirect_stdout

buffer = io.StringIO()
with redirect_stdout(buffer):
    legacy_function_that_prints()
```

它们是 process-global 的，而且不线程安全，所以应把它们限制在很窄的作用域内，而不是跨很大的区域长期保持激活。

## nullcontext

`nullcontext(value)` 是一个什么都不做的 context manager：退出时不做任何事，进入时返回 `value`。当资源可能需要管理，也可能不需要时，它可以消除分支：

```python
from contextlib import nullcontext

cm = open(path) if path else nullcontext(sys.stdout)
with cm as out:
    write_report(out)
```

这样就保留了一个 `with` 块，而不是在 `if` / `else` 中复制 body。

## closing 和 aclosing

`closing(thing)` 会在退出时调用 `thing.close()`，用于适配那些有 `close()` 方法、但自己没有实现 context manager 协议的对象。`aclosing(thing)`（3.10+）会 `await thing.aclose()`，是确定性地终结 async generator 的推荐方式。

## 常见错误：吞掉异常

contextlib 中反复出现的错误，是在 cleanup 期间静默丢弃异常。基于 generator 的 manager 会在 `yield` 后恢复控制；如果其 teardown 抛错，或者 `__exit__` 返回 truthy 值，原始错误就可能被遮蔽。`suppress` 会把这件事显式化且变成有意行为，这没问题 - 但过宽的 `suppress`、会在 `finally` 中抛错的代码，或者误返回 `True` 的 `__exit__`，都会隐藏真实失败。只抑制你理解的那个具体异常，把被抑制区域保持到最小，并且绝不要让 cleanup 代码吞掉触发它的错误。
