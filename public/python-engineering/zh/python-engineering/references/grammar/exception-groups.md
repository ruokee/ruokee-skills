# Exception Groups

`ExceptionGroup`（Python 3.11+，PEP 654）允许一次 raise 携带 _多个_ 无关异常，而 `except*` 允许 handler 只选择并处理自己关心的成员，同时让其余部分继续传播。这解决了普通异常无法解决的问题：当多个操作一起运行且不止一个失败时，普通 `try`/`except` 只能暴露第一个失败，并丢掉其他失败。

## 它解决的问题

顺序代码一次只会失败一个原因，所以一个异常就够了。并发和批处理代码则不同。如果五个下载一起运行，其中三个以不同错误失败，那么就没有单一的“那个”异常 - 丢掉其中四个会隐藏真实信息。`ExceptionGroup` 会把它们包装起来，使完整集合一起向上层传递，每个异常都保留自己的 traceback。

## 语法

`ExceptionGroup` 是一个真实的异常，包含一条 message 和一组被包含的异常：

```python
raise ExceptionGroup("download failures", [TimeoutError(...), ConnectionError(...)])
```

`except*` 按类型对 group 的 _成员_ 进行匹配。每个 `except*` 子句最多执行一次，它接收到的是匹配成员组成的 subgroup；不匹配的成员继续传播：

```python
try:
    await fetch_all(urls)
except* TimeoutError as eg:
    schedule_retry(eg.exceptions)
except* ConnectionError as eg:
    report_unreachable(eg.exceptions)
```

与普通 `except` 不同，多个 `except*` 子句可以针对一个 group 依次触发，因为 group 可能包含多种类型。绑定的名字始终是一个 group，而不是单个裸异常。

## 何时适合使用

最自然的来源是 `asyncio.TaskGroup`（3.11+）：当多个子任务失败时，group 会抛出包含这些错误的 `ExceptionGroup`。其他适用场景是批处理操作，你希望看到每个失败（验证所有字段并一起报告、处理列表项并收集所有错误），以及关闭多个资源时有多个 teardown 可能失败。

## 何时不该使用

不要把一个单独的顺序错误包装成 group。线性流程如果一次只会失败一个原因，就应当抛出和捕获普通异常 - 这里用 group 只会增加解包层数，没有任何收益。`except*` 也不是 `except` 的风格升级；在同一个 `try` 上混用二者会造成语法错误，因此引入 `except*` 是一个明确决定，意味着这个块要处理聚合失败。

## 与现有 handler 的交互

普通的 `except SomeError` **不会** 捕获隐藏在 `ExceptionGroup` 中的 `SomeError` - group 的类型是 `ExceptionGroup`，而不是 `SomeError`。采用 `TaskGroup` 的代码必须把 `except` 子句改成 `except*`，或者显式捕获 `ExceptionGroup`，否则异常会漏掉。反过来，`except*` 可以捕获 `ExceptionGroup` 本身，但这个结构的设计重心仍然是匹配成员类型。

## 嵌套行为

group 可以嵌套。用 `except*` 拆分 group 会保留结构：匹配成员会以与原始嵌套相对应的 group 形式出现，未匹配的剩余部分则作为另一个 group 继续传播，并保留自己的结构和 traceback。你很少手工构造嵌套 group - 它们通常在多个 `TaskGroup` 层级传播时出现。`BaseExceptionGroup` 是可以容纳 `KeyboardInterrupt` 等 `BaseException` 子类的变体；`ExceptionGroup` 仅限于 `Exception`，也是应用代码通常使用的类型。

如果想在 group 内为每个错误附加更丰富的上下文，可以在抛出前对单个成员调用 `add_note()`，这样每个异常都会连同 traceback 一起保留自己的解释。
