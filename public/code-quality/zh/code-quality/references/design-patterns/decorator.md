# Decorator Pattern

本文档讲的是 GoF 的 _结构型_ Decorator 模式 - 通过包装对象来添加行为。它不是 Python 的 `@decorator` 语法，虽然两者有关联，下面也会讨论这种关联。

## 目的

通过把对象包进另一个共享同一接口的对象，动态地给它附加额外职责。Decorator 为扩展行为提供了比继承更灵活的替代方案，而且可以在运行时组合和堆叠。

## 解决的问题

你有一个组件，以及若干可能要独立叠加到它身上的可选行为：缓冲、压缩、加密、指标、重试。为了每种组合都去做子类会爆炸 - `BufferedCompressedStream`、`BufferedEncryptedStream`，诸如此类。Decorator 让每种行为都成为一个遵守组件接口、并委托给被包装对象的 wrapper。你在运行时通过嵌套 wrapper，按需要的顺序和组合把想要的行为叠起来。

## 结构与参与者

- **Component**：原始对象和 decorator 共享的接口。
- **Concrete component**：被装饰的基础对象。
- **Decorator**：持有一个 Component，实现 Component，并委托给被包装对象，在委托前后添加行为。
- **Concrete decorators**：每个添加一种职责。

因为每个 decorator 都实现同一个 Component 接口并持有一个 Component，所以 decorator 和基础对象可以互换，并且可以任意嵌套。`Compress(Encrypt(FileStream(path)))` 本身也是一个 `Component`。

## Python 习惯写法

当“组件”是一个函数或可调用对象时，Python 的 `@decorator` 语法可以直接表达这个模式，也是最符合习惯的选择：

```python
def with_metrics(handler: Handler) -> Handler:
    @functools.wraps(handler)
    async def wrapped(request: Request) -> Response:
        with timer("handler.duration"):
            return await handler(request)
    return wrapped
```

`functools.wraps` 会保留被包装 callable 的名称、文档字符串和签名元数据 - 省略它会破坏 introspection 和工具支持。

当你包装的是一个有状态、方法很多的对象，并且需要在运行时组合行为时，完整的 _对象_ 形式就值得写：

```python
class Stream(Protocol):
    def read(self, n: int) -> bytes: ...
    def write(self, data: bytes) -> int: ...


class CompressingStream:
    def __init__(self, inner: Stream) -> None:
        self._inner = inner

    def read(self, n: int) -> bytes:
        return decompress(self._inner.read(n))

    def write(self, data: bytes) -> int:
        return self._inner.write(compress(data))
```

对于接口很大的对象，如果你只修改少数方法，`__getattr__` 可以把其余调用转发给内部对象 - 很强大，但也很魔法，所以要谨慎使用并写清楚文档。

## 何时使用

- 你需要在运行时按不同组合或顺序叠加独立行为。
- 这些行为是横切的且稳定：日志、缓存、重试、auth、验证、指标、transaction boundaries。
- 如果靠继承去覆盖每种组合，类数量会爆炸。

## 何时不要用

- 只需要添加一个固定行为，而且没有运行时组合需求 - 一个普通 `@decorator` 函数，或者直接内联这个行为，都比对象 decorator 层级简单。
- 新增行为需要 resource lifecycle（acquire/release）。context manager 比 decorator 更清楚地表达 setup 和 teardown。
- 你想用 decorator 去加真正的业务逻辑。decorator 应当保持薄；业务规则属于 component。

## 失效模式

- **隐藏控制流**：层层叠叠的 decorator 让执行顺序、异常被捕获的位置、时间花在哪都不透明。过深的堆叠很难调试。
- **元数据丢失**：忘记 `functools.wraps` 会破坏 `__name__`、docstring 和签名。
- **行为漂移**：decorator 轻微改变了 component 的契约（返回类型、抛出的错误），导致包装和未包装对象不再可替换。
- **性能惊喜**：每一层都会增加一次调用帧，外加可能的 I/O；指标 + 重试 + 缓存 的堆叠成本可能高于操作本身。

## 与其他模式的关系

[adapter.md](adapter.md) 改变接口；Decorator 保持相同接口并添加行为。[proxy](index.md) 也用相同接口包装对象，但它控制的是 _访问_（延迟加载、权限），而不是丰富行为 - 结构几乎相同，差别在意图。串联的 decorator 看起来像 pipeline；顺序式请求处理可看 Chain of Responsibility。当行为属于 resource lifecycle 时，优先使用 context manager，而不是 decorator。
