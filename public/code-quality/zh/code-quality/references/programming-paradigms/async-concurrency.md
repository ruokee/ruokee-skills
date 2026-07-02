# Async and Concurrency

Concurrency 让程序能同时推进多件事。Python 中的 async concurrency（`async`/`await`、`asyncio`）只是多种模型中的一种，它通过在 `await` 处挂起，在单线程上交错执行多个 I/O 密集型任务。它不是 parallelism，也不是免费的：它把代码分成一个带颜色的世界，async 函数只能从其他 async 函数中被 `await`。核心设计问题不是“我怎么把它改成 async”，而是“每个 concurrent 任务是否都有明确的 owner、lifecycle 和 error-handling policy”。

## Structured concurrency

现代 async 设计里最重要的想法是 structured concurrency：一组相关任务共享同一个 scope，而且在其中所有任务都完成之前，这个 scope 不会退出。`asyncio.TaskGroup`（Python 3.11+）是标准工具，也是 Trio 中 “nurseries” 的结构类比。

```python
async def fetch_all(urls: list[str]) -> list[Response]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch(u)) for u in urls]
    return [t.result() for t in tasks]
```

`async with` 块直到所有子任务完成才会结束。如果任意任务抛出异常，组会取消其余任务并传播错误。这给 concurrent 代码提供了和普通代码块同样的保证：当你离开 scope 时，你启动的东西没有任何一个还在后台运行。任务有清晰的 owner（这个组）和清晰的生命周期（这个块）。

## Cancellation 和 timeouts

Cancellation 会以 `CancelledError` 的形式在任务的下一个 `await` 处抛入。它是控制流机制的一部分，不是应该吞掉的普通错误。如果你捕获它来做清理，之后一定要重新抛出它。压制它会破坏 timeout、`TaskGroup` shutdown，以及整个系统里的 cancellation 传播。

```python
try:
    await do_work()
except asyncio.CancelledError:
    await cleanup()
    raise  # always re-raise
```

Timeout 使用 `asyncio.timeout()`（3.11+）或 `wait_for` 表达，它们会在 deadline 到达时取消被包装的操作。设计长时间运行的操作时，要让它们定期到达一个 `await` 点，否则 cancellation 无法生效。

## Error propagation

在 `TaskGroup` 中，多个任务可能同时失败，因此错误会以 `ExceptionGroup` 形式冒出。使用 `except*` 来处理：

```python
try:
    async with asyncio.TaskGroup() as tg:
        ...
except* ValueError as eg:
    ...
```

对于普通的线性流程，你不需要 `except*`，单个被 `await` 的协程通常只会正常抛出一个异常。只有在真实存在 concurrent 失败可能时，才使用 exception groups。

## Backpressure

当 producer 的速度超过 consumer 时，无界队列会变成无界内存增长。Backpressure 是让 producer 降到 consumer 速度的机制。使用有界队列（`asyncio.Queue(maxsize=...)`），这样队列满时 producer 会被阻塞；或者使用 semaphore 来限制并发中的工作数。围绕 backpressure 进行设计，才能把一个在负载下优雅退化的 fan-out 和一个会耗尽内存或下游连接限制的 fan-out 区分开来。

```python
sem = asyncio.Semaphore(10)  # at most 10 requests in flight at once


async def fetch_limited(url: str) -> Response:
    async with sem:
        return await fetch(url)


async def fetch_all(urls: list[str]) -> list[Response]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch_limited(u)) for u in urls]
    return [t.result() for t in tasks]
```

没有这个 semaphore，100,000 个 URL 的列表会一次性打开 100,000 个 socket，从而耗尽文件描述符或远端服务器的限制。这个上限把“全部同时进行”变成了“一次十个”，这就是 backpressure 带给你的东西。

## Async 资源 ownership

在任务内部获取的资源，只有在任务正常完成或被干净地取消时才会释放，所以 async 资源必须用 `async with` 进行 ownership，并且在 cancellation 路径上也要清理。持有资源的 async generator 需要 `contextlib.aclosing()` 来保证最终化，因为挂起的 generator 可能永远不会恢复。这是 [resource-lifecycle.md](./resource-lifecycle.md) 在 async 里的体现。

## 什么时候 async 有帮助，什么时候有害

对于有大量 concurrent 操作的 I/O 密集型工作，async 是正确工具：网络请求、数据库查询、很多同时连接、向多个服务 fan-out。单线程把时间花在等待 I/O 上，而 async 让这些等待重叠起来。

当工作是 CPU 密集型时，async 会增加成本却没有收益。重计算会阻塞单个 event loop，并饿死其他所有任务；这类工作应使用进程或线程。对于简单的顺序脚本，async 也只是额外开销：如果没有可利用的 concurrency，async 只会增加有颜色函数的约束和需要管理的 runtime。不要因为 async 很时髦就把代码库改成 async；只有在它真的能利用 I/O concurrency 时，才这样做。

## 常见错误

- **Fire-and-forget。** 调用 `create_task()` 却不保留引用，也不放进 group。这个任务可能在运行中途被垃圾回收，而它的异常会消失。每个任务都需要一个 owner。
- **未处理的任务异常。** 一个异常从未被取回的裸任务会静默失败。`TaskGroup` 从设计上解决了这个问题；孤立任务则需要显式的 `add_done_callback` 处理或被 `await`。
- **阻塞 event loop。** 在协程中调用同步阻塞 I/O（`requests.get`、`time.sleep`、阻塞式数据库驱动）会冻结其他所有任务。使用 async 等价物，或者通过 `asyncio.to_thread()` 把阻塞调用交给线程。
- **吞掉 `CancelledError`**，上面已经说过，它会悄悄破坏整个 cancellation 系统。

贯穿始终的原则是：当每个任务都有 owner 和 scope 时，concurrency 才是可管理的。Structured concurrency、诚实的 cancellation 和 backpressure，就是防止“很多事同时发生”变成“很多事你已经无法交代”的办法。
