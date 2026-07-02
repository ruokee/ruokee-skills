# Decorators

decorator 是 higher-order function 的语法糖：定义上方的 `@d` 表示 `f = d(f)`。定义会在定义时刻传给 `d`，然后这个名字会重新绑定为 `d` 返回的东西。decorator 能做的一切都可以写成显式调用；这种语法存在的意义，是把变换放在读者能看到被变换对象的位置。

## 简单 decorators

不带参数的 decorator 接收一个 callable 并返回一个替代品。这个替代品通常是一个 wrapper closure，在原始函数外包一层行为：

```python
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def traced(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        log.debug("enter %s", func.__name__)
        try:
            return func(*args, **kwargs)
        finally:
            log.debug("exit %s", func.__name__)

    return wrapper
```

`ParamSpec` 和 `TypeVar` 让 wrapper 在类型检查器看来保持被包装函数的签名，因此调用者仍能看到原始参数和返回类型。

## `functools.wraps` 与签名保留

如果没有额外帮助，wrapper closure 会替换掉原始对象的身份：`__name__`、`__doc__`、`__module__`、`__qualname__`、`__annotations__` 和 `__wrapped__` 都会描述 `wrapper`，而不是 `func`。这会破坏 introspection、文档生成、打印函数名的日志，以及一些读取 metadata 的框架。

`functools.wraps`（它本身也是应用在内部 wrapper 上的 decorator）会把这些 metadata 复制过去。总是应用它。它还会设置 `__wrapped__`，这使工具可以解包到原始对象。注意，`wraps` 会复制 `__annotations__`，但它无法让 type checker 理解一个调用签名与原始函数不同的 wrapper - 这就是 `ParamSpec` 的作用。

## 带参数的 decorators

接受配置的 decorator 本质上是一个 factory：返回 decorator 的函数。这会多出一层嵌套 - 外层调用捕获参数，中间函数才是真正的 decorator，内层 closure 是 wrapper：

```python
def retry(*, attempts: int) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last: Exception | None = None
            for _ in range(attempts):
                try:
                    return func(*args, **kwargs)
                except TransientError as exc:
                    last = exc
            raise RetryExhausted from last

        return wrapper

    return decorate
```

用法是 `@retry(attempts=3)`。注意，如果写成 `@retry` 而没有调用，它会把函数本身传给 `attempts`，这是常见错误。参数应当尽量少且仅限关键字；很多选项通常意味着行为更适合显式 policy object。

## 类 decorators

decorator 也可以应用在 class 上。它接收 class object 并返回一个 class（通常是同一个，只是被修改过）。`@dataclass` 就是这样工作的：它检查 annotations 并生成 `__init__`、`__repr__` 和其他方法。class decorator 适合注册、附加 framework metadata，或者做轻量后处理。当它们以 type checker 和读者无法跟踪的方式改变构造、继承或属性时，就会变得危险。

## decorator classes

一个通过 `__call__` 变得可调用的 class 也可以作为 decorator。对于 wrapper 需要命名状态、超出单个 closure 变量的 setup，或者更清晰的对象边界时，可以考虑它：

```python
class RateLimited:
    def __init__(self, limiter: Limiter) -> None:
        self._limiter = limiter

    def __call__(self, func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            self._limiter.acquire()
            return func(*args, **kwargs)

        return wrapper
```

要区分 _decorator class_（它的 `__call__` 接受函数）和用来包装 _instance_ 的 class。前者是 decorator；后者只是普通 composition。

## 叠加与执行顺序

叠加的 decorators 在定义时自下而上应用，在调用时则由外到内执行：

```python
@cache
@retry(attempts=3)
def fetch(key: str) -> bytes: ...
```

这里 `retry` 先包装 `fetch`，然后 `cache` 再包装结果。调用时 `cache` 最外层运行，因此命中缓存会完全跳过 retry。顺序会改变行为，所以当两个 decorator 发生交互（缓存与重试、授权与日志）时，顺序是值得写注释的真实决策。

## 类型保留挑战

如果不刻意保留，wrapper 会擦除类型信息。对于保留签名的 wrapper，使用 `ParamSpec` 加返回类型 `TypeVar`。那些 _改变_ 签名的 decorators - 例如注入一个参数、改变返回类型 - 不能只靠简单的 `ParamSpec` 透传表达，需要手写返回类型或 `typing.overload`。把函数转换成另一种对象（descriptor、注册的 handler）的 decorator，应当标注新类型，这样调用者才不会被误导。

## Decorators 何时有帮助，何时有害

Decorators 适合稳定、横切的关注点，而且名字能准确说出改变内容：注册、路由、缓存（`@cache`）、重试或超时策略、授权、metrics、tracing、弃用标记。标准库还提供了几个你应该认识的：`@property`、`@staticmethod` 和 `@classmethod` 影响属性和方法绑定；`@functools.cached_property` 为每个实例做 memoize；`@dataclass` 生成样板代码；`@typing.overload` 声明多个签名；`@functools.singledispatch` 提供基于类型的分派。

它们在以下场景中会伤人：隐藏读者需要跟踪的控制流，把业务逻辑塞进没人会检查的地方，悄悄改变返回类型或吞掉异常，或者通过层层 wrapper 把真实调用埋起来，使调试变得更困难。测试标准是：如果要理解函数行为必须先读 decorator 源码，那么这个行为大概率更适合显式调用或 context manager。
