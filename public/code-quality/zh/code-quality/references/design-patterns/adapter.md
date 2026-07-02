# Adapter

## 目的

把一个已有对象的接口转换成调用方期望的接口，让原本没被设计成一起工作的两样东西能够协作，而双方都不需要修改。

## 解决的问题

你依赖了一个类 - 第三方 SDK、遗留模块、外部服务客户端、原始数据库行 - 它的接口和你的代码需求不匹配。你当然可以改写调用方去说那个“外来”接口，但那会把依赖扩散到各处，并把你的领域和一个你无法控制的形状绑死。Adapter 把不匹配限制在一个包装对象里。调用方看到的是你自己拥有的稳定接口；适配器负责翻译。

这就是 Dependency Inversion Principle 在运行时的体现：高层代码依赖它自己定义的抽象，而适配器让一个具体的外部对象满足它。

## 结构与参与者

- **Target**：客户端想要使用的接口（在 Python 里，通常是 `Protocol` 或一种非正式的 duck-typed 合约）。
- **Adaptee**：已有但接口不兼容的对象。
- **Adapter**：实现 Target，并转发到 Adaptee，在边界上翻译数据和错误。
- **Client**：使用 Target 的代码，从不见到 Adaptee。

经典区分是 **object adapter** 和 **class adapter**。object adapter 会把 adaptee 作为属性持有并委托给它；class adapter 则同时继承 target 和 adaptee。几乎所有场景都更偏好 object adapter，因为它是组合而不是纠缠继承，能够处理你并未创建的 adaptee 实例，而且还能适配多个 adaptee。class adapter 需要多重继承，并且在定义时就把你绑死到 adaptee 的类上。在 Python 里，应当优先使用 object adapter；只有在你真的需要成为 adaptee 的子类型时，才考虑继承。

## Python 习惯写法

持有 adaptee，并在边界处做翻译：

```python
class PaymentGateway(Protocol):
    async def charge(self, order: Order) -> PaymentResult: ...


class StripeGateway:
    def __init__(self, client: StripeClient) -> None:
        self._client = client

    async def charge(self, order: Order) -> PaymentResult:
        try:
            response = await self._client.create_charge(order.total_cents)
        except StripeError as exc:
            raise PaymentDeclined(order.id) from exc
        return PaymentResult.from_stripe(response)
```

适配器不一定非得是类。一个把外部 dict 映射成领域 `dataclass` 的薄函数，本身就是适配器。Duck typing 也会消掉很多适配器的需要：如果对象已经有你要调用的方法，你就不需要包装器去满足一个名义接口。

## 何时使用

- 隔离第三方 SDK、遗留 API 或外部服务，让其余代码依赖你自己的接口，而不是它们的接口。
- 把多个不同后端（支付提供方、存储驱动、通知通道）统一到一个契约之下。
- 在系统边界转换数据表示 - wire format、ORM 行、协议消息 - 变成领域类型。

## 何时不要用

- 接口本来就匹配，或者 duck typing 已经让对象可以直接使用。一个只做方法重命名的包装器纯属多余。
- 你真正想要的是一个围绕自身需求设计的新接口，而不是翻译旧接口。那就直接写这个接口，不必给旧接口穿外衣。
- adaptee 是你自己的，并且你可以修改它。直接修源头，不要永远包着一层。

## 失效模式

- **泄漏或纯转发适配器**：调用 1 对 1 原样转发，没有任何翻译，只增加了一跳和一个需要导航的文件，毫无收益。
- **过度隐藏**：把 adaptee 的错误、重试、超时和性能特征都吞掉，让调用方无法正确响应。适配器应该翻译失败语义，而不是抹掉它们 - 把 `StripeError` 映射成领域 `PaymentDeclined`，不要返回 `None`。
- **肥适配器**：不断累积业务逻辑。适配器负责翻译；一旦它开始做决策，它就已经变成别的东西了，应该据此命名。

## 与其他模式的关系

Adapter 改变接口但不改变行为；[decorator.md](decorator.md) 保持接口不变并添加行为；[facade.md](facade.md) 则在多个对象之上定义一个新的、更简单的接口，而不是翻译单个对象。Adapter 和 [strategy.md](strategy.md) 经常一起出现：适配器满足的 `Protocol` 往往就是 strategy 插入所依赖的那个抽象。对于值的类型驱动翻译，`functools.singledispatch` 可以作为一种轻量的适配器分发机制。
