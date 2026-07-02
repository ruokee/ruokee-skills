# Type Hints

现代 Python 中的类型标注既不是装饰，也不是运行时强制机制 - 它们是接口契约中可机器检查的那部分。像 `def fetch(url: str, timeout: float) -> Response` 这样的 signature，会在任何人读函数体之前就告诉调用者、类型检查器和编辑器，这个函数接受什么、返回什么。typing 的全部价值都来自把 annotations 当作边界上的契约来对待，并且诚实地划分哪些地方契约应该很强（public API），哪些地方契约故意很松（外部数据进入的脏边缘）。

## 把类型标注当作接口契约

最有价值的地方是 public surface：module-level function、class method、dataclass field，以及任何跨 module 边界被 import 的东西。带类型的 signature 是不会漂移的文档，是 IDE 自动补全的来源，也是 type checker 在运行前就能抓住误用的检查点。其收益与距离成正比 - 调用者离实现越远，annotation 的作用越大，因为调用者不会去读函数体。

在 function 内部，local variable 大多不需要注解；checker 可以推断它们，而 `count = 0` 写成 `count: int = 0` 并没有任何收益。只有在推断真的失败、变量承载了值得用类型命名的重要领域概念，或者你需要阻止 `Any` 继续传播时，才为 local 加注解。过度标注 local 只会增加噪音，而不会增加契约。

实际上的优先级顺序是：完整而精确地标注 public API。标注跨 module seam。标注复杂返回值和数据模型字段。把显而易见的 local 留给推断。这才是“full type coverage”的实际含义 - 每个边界都携带契约 - 而不是给每个绑定都机械地加一层注解。

## Type Parameters

generic 允许一个函数或 class 只写一次，并在多种具体类型下保持 type-safe。Python 3.12 的 PEP 695 语法把它变成了第一类语言特性：`def first[T](items: Sequence[T]) -> T` 和 `class Box[T]:` 可以在行内声明 type parameter，不需要 `TypeVar` import，也不需要 `Generic` base class。注解现在准确表达了旧样板代码所表达的东西 - 输出类型跟随输入类型 - 但语法更像普通代码。

```python
def first[T](items: Sequence[T]) -> T:
    return items[0]


class Box[T]:
    def __init__(self, value: T) -> None:
        self._value = value

    def get(self) -> T:
        return self._value
```

在 3.12 之前的 floor 上，同样的代码必须显式写出这些机制：

```python
from typing import Generic, TypeVar

T = TypeVar("T")


def first(items: Sequence[T]) -> T:
    return items[0]


class Box(Generic[T]):
    ...
```

当真实存在需要保留的类型关系时，generic 才值得出现：一个容器应该返回你放进去的东西，一个函数的返回类型取决于其参数类型。反射式地使用它们则会伤人。如果一个函数接受一种具体类型并返回另一种，那么它不是 generic；把它写成带 type parameter 的形式只会遮住真实类型。判断标准是这个 parameter 是否表达了调用者依赖的关系 - 如果删掉它并不会丢失调用者会用到的信息，那它只是仪式感。

当类型并不真的任意时，bound 和 constraint 可以让 generic 更精确。绑定到 `Comparable` protocol 的 `T`（`def maximum[T: Comparable](items: Iterable[T]) -> T`）表示“任何可排序类型”，而不是“字面意义上的任何东西”，这样 body 就可以使用 `<`，而 checker 也会拒绝不支持它的类型。只有当 generic body 真的依赖某种能力时才使用 bound；如果它确实不关心，则保持不加约束。

注意硬版本门槛：PEP 695 语法在 3.12 以下会直接 `SyntaxError`。floor 为 3.11 的项目仍然必须使用 `TypeVar` / `Generic`。关于 floor 如何约束可用语法，见 [python-version](../project/python-version.md)。

## Type Aliases

type alias 是给 type expression 起名字。Python 3.12 的 `type` 语句把这件事显式化了：

```python
type UserId = int
type Handler = Callable[[Request], Awaitable[Response]]
type Json = dict[str, "Json"] | list["Json"] | str | int | float | bool | None
```

当某个 type expression 很长、重复出现，或带有裸结构无法体现的领域含义时，alias 会提升清晰度。`type Handler = Callable[[Request], Awaitable[Response]]` 会让读者比原始 signature 更清楚这个 callable 是 _做什么的_；像 `Json` 这样的递归 alias，如果每次都内联出来，会难以阅读。

失败模式是 alias 把读者需要的结构藏起来。把 `int` 起名为 `Count` 往往没什么帮助：读者得到了一个名字，却失去了它是可以做算术的 `int` 这一信息；而 checker 也会把它们视为相同，因此什么也抓不到。只有当名字携带了结构本身没有的信息时才使用 alias；如果它只是给已经清楚的东西改个名字，就不要用。

如果你想要的是一个由 checker 强制区分的 _不同_ 类型 - 让 `UserId` 不能被当成 `OrderId` 传入，即使底层都是 `int` - 那应该用 `NewType`，而不是 alias：

```python
from typing import NewType

UserId = NewType("UserId", int)
OrderId = NewType("OrderId", int)
```

`NewType` 在构造时需要显式包一层（`UserId(42)`），但换来的是真正的检查收益：混用这两种类型会变成 type error。alias 是一种零检查成本的可读性工具；`NewType` 是一种带轻微使用成本的安全工具。按你真正需要的是哪一个来选。

## 渐进式 typing 策略

Python 的 type system 天生就是渐进式的：typed 和 untyped code 可以共存，而 `Any` 就是它们之间的缝隙。一个合理的策略不是“把一切都 type 到最严格”，而是“让边界足够严格，并把松散部分收起来”。public signature 和 module 边界应当完整且精确地标注。脏的内部 - 解析任意 JSON、对接未标注的第三方 library - 才是 `Any` 合法存在的地方，而目标是把它 _收住_：尽早把外部数据转换成 typed shape，这样 `Any` 就不会越过 adapter layer 漏到代码其他部分。

```python
def load_config(raw: object) -> Config:
    # `raw` arrived from json.load and is effectively Any-shaped.
    # Validate and convert at the boundary; everything downstream
    # works with the typed Config, never the raw payload.
    data = _validate(raw)
    return Config(host=data["host"], port=data["port"])
```

`Any` 的危险在于它会传染：任何触碰到 `Any` 值的表达式都会变成 `Any`，悄无声息地关闭其后所有内容的检查。调用链顶部一个未收敛的 `Any`，就足以让整个 subsystem 的契约失效。收敛 - 在第一次机会就把它缩小为 typed shape - 才能让其余代码保持诚实。

`cast` 是一个显式逃生舱：当你知道得比 checker 能证明的更多时，用它做断言 - 比如在 checker 无法跟随的运行时检查之后收窄类型，或者缩小 checker 看到的过宽值。它不会做任何运行时检查；它只是告诉 checker“这里请相信我”。这让它成为一个精确工具，而不是批量消音的手段：每个 `cast` 都是在做一个小的未检查断言，满篇 `cast` 的函数已经失去了本该提供的契约。只要有 checker 能跟踪的运行时检查，就优先使用它，而不是 `cast`：

```python
# Prefer this — the checker follows the narrowing itself:
if not isinstance(value, str):
    raise TypeError(value)
reveal_type(value)  # str

# Over this — an unchecked assertion the checker cannot verify:
value = cast(str, value)
```

## Protocol 与结构化子类型

`Protocol` 把 duck typing 形式化了。一个 class 只要拥有正确的方法和属性，就满足一个 `Protocol`，而不需要显式继承 - 这正是 Python 一直以来“只要有 `.read()`，它就是 file-like”那种推理方式，现在变得可检查了。

```python
from typing import Protocol


class Readable(Protocol):
    def read(self, size: int = -1) -> bytes: ...


def consume(source: Readable) -> bytes:
    return source.read()
```

任何具有匹配 `read` 方法的对象都满足 `Readable` - 文件、socket wrapper、内存 buffer - 它们彼此之间无需 import 或 subclass 这个协议。

当你想接受任何符合某个形状的对象时，优先使用 `Protocol`，尤其是那些你不拥有、也无法让它们继承你基类的类型。只有当你拥有这套层级、想共享实现、并且需要显式且已注册成员关系时，才选 abstract base class（ABC）。经验法则是：`Protocol` 用于结构化地接受外部形状；ABC 用于定义你可控的封闭层级。Protocol 还会把依赖箭头指向正确方向 - _consumer_ 定义它需要的窄接口，而不是逼每个 producer 都 import 并 subclass 一个基类。这是“依赖抽象”的类型化表达，也正是为什么一个放得合适的 `Protocol` 能把本会被 ABC 绑死的 module 解耦开来。

## `TYPE_CHECKING` 与运行时隔离

有些 import 只为了满足 annotation，本不该在 import 时执行 - 它们可能很重，或者会造成循环 import。`typing.TYPE_CHECKING` 常量（runtime 下始终为 `False`，type checker 下为 `True`）可以把它们隔离开：

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import User


def load(user_id: int) -> "User": ...
```

checker 会看到这个 import 并验证 annotation；解释器在运行时不会执行它。这是打断 annotation-only import cycle 和延迟昂贵 import 的首选工具，也是大多数人会想到 `from __future__ import annotations` 时的正确答案 - 它在本地解决 forward-reference 和 cycle 问题，而不需要把整个 module 绑定到 stringized-annotation 语义上。唯一的注意点是：在 `TYPE_CHECKING` 下导入的名字在 runtime 不存在，所以任何在 runtime 读取 annotations 的代码（framework、ORM、serializer、DI container）都不能用最朴素的方式解析它。若 runtime introspection 很重要，就应由 [python-version](../project/python-version.md) 中的版本特定行为来决定如何读取 annotations。

## 用 collections.abc 表达接口边界

当你描述一个 function _接受什么_ 时，优先使用 `collections.abc` 中的抽象类型，而不是具体类型。只需要遍历的函数应接受 `Iterable[T]`，而不是 `list[T]`；只需要查找的函数应接受 `Mapping[K, V]`，而不是 `dict[K, V]`：

```python
from collections.abc import Iterable


def total(values: Iterable[int]) -> int:
    return sum(values)
```

标注为 `Iterable[int]` 后，`total` 可以接受 list、tuple、generator、set，或者任何自定义 iterable - 同时这个 signature 也 _承诺_ 它只会遍历，而不会索引或修改。若把参数标成 `list[int]`，则会拒绝所有这些调用者，并且过度声称函数内部能做什么。

return value 和你拥有的 field 应该使用具体的 `list` / `dict` 类型，因为调用者会从明确知道自己拿到的 exact type 中获益。这个原则与一般的接口设计一致：接受满足你所需能力的最不具体类型，返回你能够承诺的最具体类型。优先使用 `collections.abc` 的形式（`Iterable`、`Sequence`、`Mapping`、`Callable`），而不是已经废弃的 `typing` 别名。

## 静态类型检查

静态类型检查器在不运行代码的情况下读取 annotations，在执行前就能抓住契约违反。大多数项目所说的“类型检查”默认指的就是它。存在多个工具，应选择其中一个作为门禁，而不是默认全部运行。

- **mypy** —— 成熟、被广泛采用的 checker，拥有最深的生态和强大的 strict mode，是主流选择，尤其适合 library 工作和外部协作。部分项目会 mypy 与 pyright 联用，兼得 mypy 的深度推断和 pyright 更快更严的反馈。
- **pyright** —— 微软出品的高速、严格 type checker。它也是 **Pylance**（VS Code Python language server）的底层引擎，因此很多编辑器在你输入时就会实时呈现 pyright 的结果。
- **basedpyright** —— pyright 的更严格、有主见的 fork，适合作为严格交叉检查。它和 **ty** 都可以作为 Zed 等编辑器的 LSP。
- **ty** —— 快速、集成 LSP 的 checker，面向紧密的编辑反馈回路和 CI。它较新，成熟过程中偶有行为变化，采用时应是有意识的、持续关注的选择。

项目选其一作为门禁；在迁移、发布或需要调和某个棘手 inference 差异时，可临时启用第二个。各工具的详细选择与配置取舍放在工具参考里（[mypy](../tooling/mypy.md)、[basedpyright](../tooling/basedpyright.md)、[ty](../tooling/ty.md)）。规范层面最重要的是：annotations 要写成一份连贯的契约，checker 的选择是其上的另一层项目级决策。好的 typed code 不会绑定到某一个 checker；它表达的是任何合格 checker 都能验证的一份清晰契约。

## 运行时类型检查

静态检查在不被信任的数据进入处就止步了：JSON payload、请求体、配置文件、网络响应。运行时类型检查器在边界把这些数据校验并转换成 typed shape，使后续代码操作的是已校验的值，而不是 `Any`。**Pydantic**、**msgspec** 等库是常见代表：声明一个带标注字段的 model，把原始数据传入，拿回一个已校验实例（或带精确错误的拒绝）。检查发生在数据越过边界时，而不是每次调用。

它补充而非替代静态类型检查：model 定义本身带 annotation，静态检查器仍能推断字段；而运行时检查保证真实进入的数据符合形状。把它用在外部数据到达的边缘；不要散布在已经静态标注并被信任的内部代码中。
