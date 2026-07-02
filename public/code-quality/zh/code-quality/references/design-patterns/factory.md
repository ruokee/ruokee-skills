# Factory Method

## 目的

把对象创建与使用对象的代码解耦。调用方按意图请求一个 product（“给我一个这个格式的 parser”），而不必命名具体类，也不需要知道它如何组装。

## 解决的问题

构造逻辑很容易渗进调用方：选哪个具体类、如何验证输入、如何连线依赖、应用哪些默认值。当同样的 `if kind == ...: return SomeClass(...)` 片段在多处出现时，构造规则一变，就得改每个调用点。Factory Method 把这个决策集中到一个地方，并给它起名字。

## 结构

在经典 GoF 形式里，`Creator` 声明一个返回 `Product` 的 factory method，子类覆盖它来决定具体 product。参与者是抽象 creator、具体 creators、product 接口和具体 products。

在 Python 里，这整套层级很少是最佳形状。“creator”通常只是一个普通函数、一个 `classmethod`，或者一次 registry 查询。只有当框架把创建步骤定义成扩展点，并且你的子类确实需要覆盖它时，子类覆写方法这套形式才有存在价值。

## Python 习惯写法

优先使用普通 factory function：

```python
def make_parser(kind: str) -> Parser:
    match kind:
        case "json":
            return JsonParser()
        case "yaml":
            return YamlParser()
        case _:
            raise UnknownParserError(kind)
```

对于由配置或插件驱动的创建，registry 可以让工厂在不修改分发逻辑的情况下保持可扩展：

```python
_PARSERS: dict[str, Callable[[], Parser]] = {}

def register_parser(kind: str, factory: Callable[[], Parser]) -> None:
    _PARSERS[kind] = factory

def make_parser(kind: str) -> Parser:
    try:
        return _PARSERS[kind]()
    except KeyError as exc:
        raise UnknownParserError(kind) from exc
```

`classmethod` 风格的替代构造器（`Model.from_dict`、`datetime.fromtimestamp`）是 Python 最常见的工厂形式：类自己拥有一组命名方式来构建自己。

## 何时使用

- 具体类型取决于运行时值：文件格式、协议名、配置项、插件名。
- 构造涉及验证、依赖连接，或者默认 strategy 选择，不想在调用点重复。
- 现在已经有多个真实实现，或者有明确的扩展点（插件、entry points）。

## 何时不要用

- 只有一个实现，而且构造很简单 - 直接调用构造函数即可。
- 一个一行 `if` 或直接实例化就能完成。把它包进抽象 creator 层级只会增加间接层，却没有任何变化。
- 所有构建对象的地方都被命名成 `Factory`，把这个概念稀释到失去意义。

## 失效模式

- 一棵 Java 风格的抽象 creator / 具体 creator 树，而函数就足够了，迫使读者穿过层层子类才能找到一个 `return`。
- factory function 悄悄吞掉未知 kind 并返回默认值，掩盖配置错误。应当抛出清晰的领域错误。
- 工厂开始长出副作用（日志、I/O、注册），导致构造不再纯粹或可预测。

## 与其他模式的关系

[abstract-factory.md](abstract-factory.md) 把这个思想扩展到必须一起变化的整套 product。[builder.md](builder.md) 处理的是复杂的分步构造，而不是“选哪个类”。当 product 由一个运行时值选择，而这个值也驱动后续行为时，这个选择可能其实更适合放在 [strategy.md](strategy.md) 中。`functools.singledispatch` 是一个相关的 Python 机制，当创建需要按参数类型变化时尤其有用。
