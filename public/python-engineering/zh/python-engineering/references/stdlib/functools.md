# functools

`functools` 提供高阶 helpers：接收或返回函数的工具。它们减少了分派、部分应用、memoization 和 decorator 编写中的样板代码。下面每个 helper 都针对不同需求；当手工替代方案更容易出错时再使用它们，而不是默认就用。

## singledispatch

`@singledispatch` 会把一个函数变成 generic function，根据其 _第一个_ 参数的运行时类型选择实现。可以通过 `.register` 注册类型特定变体：

```python
from functools import singledispatch

@singledispatch
def render(value: object) -> str:
    raise TypeError(f"no renderer for {type(value).__name__}")

@render.register
def _(value: int) -> str:
    return f"int:{value}"

@render.register
def _(value: list) -> str:
    return "[" + ", ".join(render(v) for v in value) + "]"
```

自 Python 3.11 起，注册的 annotation 可以是 union（`int | float`），这样一次注册就能覆盖一类类型。`singledispatch` 适合开放扩展：新类型可以添加 handler，而无需编辑中心函数 - 这是一种轻量 visitor。它 _不会_ 根据第二个参数、字段值或组合来分派；那些情况需要显式分支、`match`，或 dispatch map。方法应使用 `singledispatchmethod`。基础实现应当有意义（合理的默认行为或清晰的错误），因为当没有注册类型匹配时，它就会被调用。

## partial

`partial` 会为 callable 绑定一部分参数，生成一个只需要剩余参数的新 callable。它可以在没有 wrapper `lambda` 或 closure 的情况下捕获上下文：

```python
from functools import partial

def connect(host: str, port: int, *, timeout: float) -> Connection: ...

connect_local = partial(connect, "localhost", timeout=5.0)
conn = connect_local(8080)
```

当你只是固定参数时，优先使用 `partial` 而不是 `lambda` - 它是可 pickle 的、可 introspect 的（`.func`、`.args`、`.keywords`），并且表达的是意图。类型检查器对复杂签名下的 `partial` 结果推断并不完美，因此当推断类型不清晰时，应在绑定位置加注解。它适合 callbacks、依赖注入，以及为特定调用点配置通用函数；不要把许多 `partial` 叠成一条难以理解的链。

## lru_cache / cache

`@lru_cache(maxsize=...)` 会按参数对结果做 memoize；`@cache`（3.9+）等价于 `lru_cache(maxsize=None)` - 即无上限 memo。它们能加速纯函数、且带有可哈希参数的重复调用：

```python
from functools import cache

@cache
def factorial(n: int) -> int:
    return 1 if n <= 1 else n * factorial(n - 1)
```

只有当函数是 referentially transparent 时，cache 才是正确的：相同输入，相同输出，没有可观察的副作用。对非纯函数（读文件、时钟、可变全局状态）做缓存，会掩盖过时数据的 bug。还有两个风险：在长期运行进程上使用无上限 `@cache` 会造成内存泄漏，而把 cache 放在 method 或任何持有 object 引用的函数上，会让该 object 一直存活。参数必须可哈希，因此像 list 或 dict 这样的不可哈希输入无法直接缓存，必须先转换。当输入种类很多时，用 `lru_cache(maxsize=...)` 限制大小，并在测试中暴露 `.cache_clear()`。

## reduce

`reduce` 会把一个 binary function 在 iterable 上折叠成单一值。对于那些没有内建函数可用的真正聚合场景，它是可读的：

```python
from functools import reduce
from operator import or_

merged = reduce(or_, dict_list, {})  # union of many dicts
```

如果已经有普通 `for` loop 或内建函数（`sum`、`math.prod`、`any`、`all`、`"".join`），就优先用它们 - 对大多数读者来说更清楚。`reduce` 只有在 associative 组合场景中才值得使用，即在 loop 里给中间 accumulator 起名并不会更清楚的时候。`reduce` 中嵌套的 `lambda` 往往是一个信号：该改回显式 loop 了。

## wraps

`@wraps(func)` 会把被包装函数的身份（`__name__`、`__doc__`、`__module__`、`__qualname__`、`__annotations__` 和 `__wrapped__`）复制到 wrapper 上。每一个手写且返回内部函数的 decorator 都应当应用它：

```python
from functools import wraps

def logged(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

如果没有 `wraps`，introspection、文档工具、`help()` 和测试报告看到的都会是 wrapper 的身份，而不是原始函数。`__wrapped__` 也让工具可以解开到底层函数。更广泛的 decorator 机制见 [`../grammar/decorator.md`](../grammar/decorator.md)。
