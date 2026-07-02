# Functional Core, Imperative Shell

## 它是什么

Functional Core, Imperative Shell 是 Gary Bernhardt 推广的一种架构。它把程序分成两层，且两层遵循不同规则。_core_ 保存纯粹的 decision logic：给定输入 data，它计算输出 data，并且不产生任何副作用——没有 I/O、没有时钟读取、没有随机性、没有网络、没有 database、没有全局 mutation。_shell_ 则是与外部世界对话的薄薄 imperative 层：它读取输入，调用 core 决定应该发生什么，然后执行 core 要求的那些副作用。

其中的洞见是，让代码变得难以测试、难以推理的，几乎从来不是算术或分支本身，而是对环境的依赖。一个决定订单能否发货的 function 很容易测试；一个既决定又去扣卡、写行、发邮件的 function 就不容易了。把环境推到边缘，真正有趣的 logic 就会变得 pure、total，而且可以极其简单地测试。

这不是 Python 的官方概念，但它与 Python 的 multi-paradigm 风格，以及 [imperative.md](./imperative.md) 中描述的 entry-point boundary discipline 自然契合。

## 其背后的假设

- 系统里最难测试的部分不是计算，而是副作用和环境耦合。
- 一旦副作用被推到边界，core 就可以用普通 data in、data out 的方式测试，不需要 mock、fixture，也不需要 patch clock。
- Shell 仍然需要认真设计，因为 transactions、retries、error handling、logging 和 resource lifecycle 都在那里。

## 好处

- **Testability.** Core tests 是 example-based 的：传入 data，断言返回 data。没有 I/O 设置，没有 mock framework，速度快且确定。这是最大的收益。
- **Reasoning.** 一个 pure function 的行为完全由它的参数决定。你可以独立理解它，而无需追踪它接触了哪些全局 state 或外部 service。
- **Composability.** Pure functions 可以干净地组合——一个的输出成为下一个的输入，不存在隐藏的顺序约束。Shell 只负责显式地排列那些不纯步骤。

## 何时适用

凡是有趣的 decision 可以与执行动作分离的地方，都适合使用它：

- Domain rules：pricing、eligibility、permission checks、state transitions（见 [state-machine.md](./state-machine.md)，其中 `(state, event) -> new_state` reducer 就是 textbook functional core）。
- 在数据触及 persistence 之前，对 input 做 validation 和 normalization。
- Data transformation pipelines，其中 transform rules 是 pure 的，而只有读写两端是不纯的。
- CLI 和 request handlers：shell 解析 arguments 或 HTTP，组装 dependencies，调用一个纯 planner；core 返回一个 decision 或需要执行的工作描述。

一种有用的形状是让 core 返回一个对副作用的 _description_（commands 列表、event、typed result），由 shell 去执行它们。core 做决定；shell 执行。

```python
# core: pure, no I/O — trivial to test with data in, data out
def plan_discount(cart: Cart, customer: Customer) -> DiscountPlan:
    if customer.tier == "gold" and cart.total > 100:
        return DiscountPlan(percent=15, reason="gold-large-order")
    return DiscountPlan(percent=0, reason="none")


# shell: imperative, owns I/O, transactions, logging
def apply_discount(cart_id: str, customer_id: str) -> None:
    cart = repo.load_cart(cart_id)          # I/O
    customer = repo.load_customer(customer_id)  # I/O
    plan = plan_discount(cart, customer)    # pure decision
    repo.save_discount(cart_id, plan)       # I/O
    logger.info("applied %s", plan.reason)  # I/O
```

`plan_discount` 的测试只需要构造一个 `Cart` 和 `Customer`，调用函数，然后断言返回的 `DiscountPlan`——不需要 database，不需要 mocks，也不需要 patch clock。这个 discount 规则的每个分支都能用一行 setup 触达。相比之下，shell 可以用少量 integration tests 来验证，或者本身薄到直接阅读就足够。

## 当严格 purity 适得其反时

- **I/O-heavy glue code.** 这类代码的全部职责就是在两个系统之间搬运 bytes，几乎没有可提取的 pure decision。强行套 functional core 只会得到一个空洞的 core 和一个掩盖真实复杂度的厚 shell。
- **Simple CRUD.** 当操作只是“读一行、改一个字段、写回去”时，没有什么有意义的 decision 可抽。直接的 imperative function 更清楚。
- **Copy-cost-heavy data.** 严格的 purity 不允许 mutation，所以一个天真的 core 可能会反复复制大型结构。当这个代价占主导时，可以在一个总体仍然是 pure 的 function 内部允许局部 mutation，或者在那个 seam 放宽 purity。
- **Anemic cores.** 如果拆分之后只剩下一张由极小 pure functions 组成的迷宫，它们已经不再讲 domain language，你就是拿清晰度换教条了。让 core 继续用 domain terms 来表达。

需要警惕的失败模式是：shell 变得太薄，以至于 transactions、error handling 和 observability 无处安放，只好又流回 framework callbacks 里。Shell 是一个真实层次，不只是个 wrapper。

## 边界应该画在哪里

把线画对，是整个技巧所在。seam 应该恰好落在基于手头已有 data 做出 decision 的地方。先把这个 decision 需要的东西全部读出来，再在 core 中做决定，然后根据这个决定去执行动作——不要把读取与决策交错在一起，因为每多读一次进入逻辑中间的东西，环境就会被拖回 core。

一种常见的改进方式，是让 core 返回描述 effects 的 data，而不是一个裸 value：

```python
# core returns a description of what should happen — still pure
def plan_effects(order: Order, now: datetime) -> list[Effect]:
    if order.is_overdue(now):
        return [ChargeLateFee(order.id), NotifyCustomer(order.id, "overdue")]
    return []


# shell interprets the descriptions — the only place effects actually fire
def process(order_id: str) -> None:
    order = repo.load(order_id)
    for effect in plan_effects(order, datetime.now(tz=UTC)):
        execute(effect)
```

现在，甚至“要执行哪些 effects”的选择也可以在不真正执行它们的情况下测试：断言返回的 list 即可。Shell 收缩成一个笨拙的 interpreter，而有趣的 branching 全部留在 core 里。这和 [state-machine.md](./state-machine.md) 中 reducer 返回 `(next_state, actions)` 的形状是一致的。

`datetime.now(tz=UTC)` 这个 clock 是在 shell 中读取的，然后作为 `now` 传入 core。正是这个动作，才让与时间相关的规则保持 pure 且可确定测试。

## 在 Python 中

- Entry layers 可以使用 argparse、Click、Typer、FastAPI 或 Django，但 core business functions 不应依赖 framework objects——在边界上传递普通 data。
- 把边界 data 放在 `dataclass`、`TypedDict`、Pydantic model 或普通 dict 中，依据项目复杂度选择（见 [data-oriented.md](./data-oriented.md)）。
- 不稳定的依赖——clock、randomness、filesystem、HTTP client、database session——应以函数参数、构造参数、一个小 `Protocol`，或通过 composition root 注入，而不是在 core 内部直接获取。
- Core 应该接收普通 data 并返回普通 data；shell 负责 `with` / `async with` 的 resource lifecycles（见 [resource-lifecycle.md](./resource-lifecycle.md)）。

## 与其他 paradigms 的关系

- 直接建立在 [imperative.md](./imperative.md) 上：shell 本身就是刻意保持很薄的 imperative orchestration layer。
- Pure core 是 [data-oriented.md](./data-oriented.md) 思维发挥作用的地方——plain data in，plain data out。
- 对于 lifecycle logic，core 中的 pure reducer 加上执行 effects 的 shell，是构建 [state-machine.md](./state-machine.md) 最清晰的方式。
