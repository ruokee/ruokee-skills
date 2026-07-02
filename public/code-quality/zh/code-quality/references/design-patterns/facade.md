# Facade

## 目的

为复杂子系统提供一个单一、简单的接口。Facade 定义一个更高层的入口，让子系统更容易使用，同时又不妨碍需要更细粒度控制的调用方直接接触底层各部分。

## 解决的问题

一个子系统会累积很多必须按正确顺序协调的类和步骤：获取客户、根据订单行创建发票、发布事件、更新账本。如果每个调用方都自己编排这些步骤，协调逻辑就会被重复，调用代码会耦合到内部结构，而工作流一旦变化就意味着要改每一个调用点。Facade 给常见用例起一个名字（“给这个订单开票”），并把编排责任集中到一个地方。

## 结构与参与者

- **Facade**：暴露少量高层操作，并委托给子系统对象，负责安排它们的交互顺序。
- **子系统类**：真正干活的类；它们并不知道 facade 的存在，仍然可以直接使用。

Facade 不增加任何新功能 - 它只是把已有部件组合成一个更方便的表面。调用方依赖 facade；facade 依赖子系统。

## Python 习惯写法

模块本身就是天然的 facade：一个带有精选 `__all__` 的包 `__init__.py` 可以暴露少量入口函数，而实现细节留在私有子模块里。

当多个用例共享状态或依赖时，一个 client class 很合适：

```python
class BillingClient:
    def __init__(self, customers, invoices, events) -> None:
        self._customers = customers
        self._invoices = invoices
        self._events = events

    async def invoice_order(self, order: Order) -> Invoice:
        customer = await self._customers.get(order.customer_id)
        invoice = await self._invoices.create(customer, order.lines)
        await self._events.publish(InvoiceCreated(invoice.id))
        return invoice
```

一个好的 facade 是一个 _deep module_：在大量内部复杂性前面放一个小接口。正因为它真的隐藏了很多工作，它才值得存在 - 不是只挡住几行代码。

## 何时使用

- 多步工作流或第三方 SDK 在多个地方被同样使用，而且你想要一个命名的入口点。
- 你希望把调用方与子系统的内部结构解耦，让它能在稳定表面之后演化。
- 你在做分层系统，并希望每一层都对上一层暴露一个最小接口。

## 何时有害

- **隐藏了调用方真正需要的复杂性。** 如果调用方必须控制重试、分页、部分失败或 transaction boundaries，那么一个把这些都抹平的 facade 会迫使他们绕过它或曲线处理。应当暴露调用方必须理解的内容。
- **浅外观。** 如果它只是把一次调用转发到一个子系统方法，那它只是多了一层和一个名字，并没有隐藏任何东西。成本（额外一跳、一个要找的地方）超过了收益。
- **god object。** 一个逐渐覆盖系统中所有操作的 facade 会变成垃圾场，把无关用例耦合在一起，并累积对一切的依赖。

## 失效模式

- facade 在签名里泄漏了子系统类型，调用方最终还是被内部细节绑住，抽象只是幻影。
- 错误处理把不同的子系统失败收缩成一个不透明异常，导致调用方无法做出合适响应。
- facade 成了唯一允许的路径，阻断了合理的高级用法，而不是作为方便的默认路径同时保留直接访问。

## 与其他模式的关系

[adapter.md](adapter.md) 改变接口以匹配调用方预期；Facade 则在多个对象之上定义一个 _新的、更简单的_ 接口 - Adapter 是把一个东西包装成“适配”，Facade 是把多个东西包装成“简化”。facade 往往位于 [abstract-factory.md](abstract-factory.md) 前面，或者协调由 factory 构建出的对象。好的 facade 背后的“deep module”思想，与设计原则参考中的信息隐藏原则相关。它也可以和 Mediator 对比：Mediator 同样集中交互，但允许被协调的对象通过它互相对话；而 facade 则是一个单向的简化入口。
