# State Machine / Finite-State Model

State machine 把一个过程建模为有限个命名 state、一个事件集合，以及管理它们之间移动的规则。它回答的不是“class 还是 function？”而是：系统此刻能处于哪些 states，它接受哪些 events，哪些 transitions 是合法的，非法 transitions 如何被拒绝，以及在 transition 时会触发哪些 side effects。这是日常工程中最有杠杆的一种模型，因为很多 bug 本质上都是非法 state bug，只是换了身衣服。

它不是 GoF State pattern 的同义词。那个 pattern 只是 state machine 的一种 object-oriented implementation。这个 model 更广，可以用 transition table、`Enum` 加 dispatch、`match` statement、pure reducer function 或 state objects 来表达。

## 概念

State machine 将 workflow 视为 data：一个事物可以占据的 modes、推动它移动的 triggers，以及对所有不允许情况的 policy。把合法移动显式化，会让“我们忘了处理一个 cancelled order 被 pay 了”的问题，从潜在的 production bug 变成一个你能看见、能审查的单条缺失 table entry。

## 核心模型

- **State** — 系统所处的一个命名且互斥的 mode（`draft`、`submitted`、`paid`）。任何时刻它只会处于其中一个。
- **Event** — 一个命名触发器，可能引发 transition（`submit`、`pay`、`cancel`）。Events 是从机器外部到来的 facts 或 commands。
- **Transition** — 针对某个 event，从一个 state 到另一个 state 的合法移动：`(state, event) -> next_state`。
- **Guard** — transition 的前置条件。即便 transition 存在，guard 也可以阻止它：余额足够、权限有效、resource 仍然存在。
- **Action** — transition 发生时执行的 side effect：写 database、发送 message、emit event、记录 audit entry。
- **Invalid transition handling** — 对当前 state 不接受的 event 所采取的显式 policy：raise、reject 或 no-op。这是一个决策，而不是一个会静默什么都不做的未处理分支。

## 何时适用

- States 是有限的，而且可以命名；events 也是有限的，而且可以命名。
- 非法 transitions 很重要——从 `cancelled` 到 `shipped` 必须是不可能的，而不仅仅是不太可能。
- 生命周期正确性是 domain 的一部分：orders、approvals、subscriptions、protocol/connection state、job 和 worker lifecycles。
- 你需要审计为什么 `A -> B` 被允许，而 `A -> C` 不被允许，尤其是在合规场景下。
- 这个过程会与 persistence、retry 或 concurrency 交互，而精确的“当前 state”概念可以防止 corruption。

## 何时不适用

- 一个简单的线性流程，没有分支，也没有非法步骤的概念。
- 极小且显而易见的分支，用一个 boolean field 或一个单独的 `if` 就已经足够清楚。
- 没有真正的非法 state 概念——任何 value 跟任何 value 之间都可以互相转移而不会出问题。
- 为一个两状态问题提前建一个每个 state 一个 class 的方案；那是 class explosion，不是建模。

## 典型实现

- **Enum + transition table** — 一个 `dict[(State, Event), State]`。规则稳定时，这是最清晰的默认方案。易于一眼审查，也极易测试。
- **Pure reducer** — 一个没有副作用的 `(state, event) -> new_state` 函数，因此 imperative shell 负责 actions。它与 [functional-core.md](./functional-core.md) 天然搭配。
- **`match`/`case`** — 适合局部、结构化且分支不多的 transitions。它是表达 transitions 的语法，而不是 state machine 本身。
- **Dispatch map** — 当每个 event 都带有不同的处理 logic 时，使用 `dict[Event, Callable]`。
- **State objects（GoF State）** — 当每个 state 确实有大量差异化 behavior 时适用（connection states、editor modes、protocol phases）。
- **Library / workflow engine** — 当你真的需要 persistence、visualization 或 dynamic configuration 时才使用，而不是为了想象中的需求。

## 状态设计

- States 必须**互斥**。如果两个状态可以同时为真，那它们就不是同一个 machine 的 states，而是两个 machine，或者两个维度。
- 用**domain terms** 命名 states（`awaiting_payment`），而不是 implementation terms（`flag2_set`）。
- **避免把 boolean 组合当作隐式 state。** `is_active`、`is_locked`、`has_failed`、`is_retrying` 这四个独立 booleans 会编码出 16 种组合，其中大多数是非法的，也没有定义。把它们收敛到一个命名的 state enum 里。
- 将 **events** 建模为动词或事实（`pay`、`OrderPaid`），与 states 区分开。把两者混为一谈（“the `paying` event”）是模型混乱的迹象。

## Transition Table / Diagram

每个非平凡 workflow 都应该有显式的 transition table 或 diagram。它可以是代码（程序实际执行的字面 dict）或文档（Markdown table 或 state diagram）。代码形式最好，因为它不会和行为漂移。重点是：任何人都能一次性看到全部合法移动，并问一句“这完整吗？这正确吗？”，而不必沿着散落在代码库各处的条件判断追踪。

```python
from enum import StrEnum


class Order(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PAID = "paid"
    CANCELLED = "cancelled"


class Event(StrEnum):
    SUBMIT = "submit"
    PAY = "pay"
    CANCEL = "cancel"


TRANSITIONS: dict[tuple[Order, Event], Order] = {
    (Order.DRAFT, Event.SUBMIT): Order.SUBMITTED,
    (Order.SUBMITTED, Event.PAY): Order.PAID,
    (Order.DRAFT, Event.CANCEL): Order.CANCELLED,
    (Order.SUBMITTED, Event.CANCEL): Order.CANCELLED,
}


class InvalidTransition(ValueError):
    pass


def apply_event(state: Order, event: Event) -> Order:
    try:
        return TRANSITIONS[state, event]
    except KeyError as exc:
        raise InvalidTransition(f"{state} cannot handle {event}") from exc
```

## Review Model

审查 state machine 时，按以下顺序分三遍看：

1. **Completeness** — 是否枚举了所有 states？所有 events？每个 `(state, event)` 对是否都对应一个有意的 transition 或有意的 rejection？terminal states 是否被识别出来（`closed`、`cancelled` 不再接受后续输入）？
2. **Correctness** — guards 是否正确且完备？actions 是否幂等，以避免重放或重试的 event 造成双扣费或重复发送？并发应用是否安全（两个 events 是否会在同一实体上竞争）？
3. **Representation** — 只有到这一步，才讨论 table、`match` 还是 state objects 更适合表达它。先把 model 做对，再争论形式。

## 识别信号

当你看到这些情况时，就该考虑这个模型：

- status strings 在散落各处被赋值，却没有一个地方定义合法集合。
- Boolean flags 的组合在充当 state，而且没有强制的合法组合。
- `if/elif` ladders 同时检查 current state 和 incoming event，并在多个 function 中重复出现。
- 重复的 event 导致重复的 side effects——这说明 actions 不是幂等的，transitions 也没有被正确门控。

## 误判边界

单独一个 status enum **并不是** state machine——在有 transition rules 管理它如何变化之前，它只是一个命名值。把 transition table 加到真正极其简单的分支里，是过度设计；如果只有一条显而易见的线性路径，也不存在非法 state 问题，那么 table 就只是 ceremony。这个模型只有在非法 transitions 真实存在、正确性重要时才值得。把它用在那里，而不是每个出现 status field 的地方。关于 state 和 behavior 何时适合放进 object，见 [object-oriented.md](./object-oriented.md)；关于 table 形式为什么如此易于审查，见 [declarative.md](./declarative.md)。
