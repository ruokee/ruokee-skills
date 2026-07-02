# Event-Driven Architecture

## 它是什么

Event-driven architecture 把 event 视为第一类事实：某件事发生了，这个事实被记录并发布，而不是直接触发一段已知代码。producer 发出一个 event（`OrderPaid`、`FileUploaded`、`user.signup`），而不需要知道或关心谁会消费它。consumers 订阅它们关心的 events。两者之间的 coupling 是 event schema，而不是直接的 function call。

它会出现在很多尺度上：进程内的 signals 和 hooks（Django signals、pytest hooks、Qt signals）、应用内的 pub/sub，以及跨 services 的 message queues 或 event buses（Kafka、RabbitMQ、SQS、Redis streams）。统一思想是一样的：反转 dependency，让导致状态变化的东西不再持有对所有必须做出反应者的引用。

## 其背后的假设

- Producers 和 consumers 会因为不同原因而变化，因此应该能够独立部署、独立测试、独立推理。
- “发生了什么” 比“调用这个特定 handler” 更耐久。新的 reactions 可以在不修改 producer 的情况下被添加。
- 对某些系统来说，event log 本身就有价值：append-only 的事实记录天然就是 audit trail，也是 replay 的基础。

## 何时适用

- **将 producers 与 consumers 解耦。** 一个动作需要触发多个互不相关的 reactions（发送邮件、更新 analytics、使 cache 失效），而你不希望源代码知道它们全部。
- **Audit trails 和 event sourcing。** events 的序列本身就是 source of truth；当前状态只是一个 projection。这样可以 replay、做 temporal queries，并天然拥有 audit history。
- **Asynchronous workflows。** 不应该阻塞 request path 的工作——通知、索引、下游处理——很自然地可以表达为“emit event，让 worker 处理它”。
- **扩展点。** Plugins 和 hooks 允许第三方在不修改核心代码的情况下，对 lifecycle events 做出反应。

## 风险

Event-driven systems 用解耦换取了 explicit control flow，而这种交换是有真实成本的：

- **Hidden control flow。** 你无法只看 producer 就知道接下来会发生什么；reactions 在别处。这和 [declarative.md](./declarative.md) 中提到的调试困难一样，只是更强烈——call graph 是在 runtime 通过 subscriptions 组装出来的。
- **顺序与投递。** Events 可能乱序到达、重复投递，或者丢失。consumers 通常必须是 idempotent 的（同一个 event 处理两次不会产生额外影响）——这也是 [state-machine.md](./state-machine.md) 在重复 events 时所需要的属性。
- **错误上下文。** 当 consumer 失败时，失败在代码和时间上都离 producer 很远。重建“是什么导致了这次失败”需要 correlation IDs 和良好的 event metadata。
- **Event storms / cascades.** 一个 event 触发 handlers，而这些 handlers 又 emit 更多 events，再触发更多 handlers。如果不加小心，这会无限 fan-out，甚至形成 cycle。

## Consumer 失败与 delivery guarantees

直接 function call 的 failure path 很明显：caller 看见 exception。event 没有这种清晰度，因此 consumer failure 需要明确 policy。设计由三个问题决定：

- **当 consumer 抛出异常时会怎样？** 在同步的进程内 bus 中，一个失败的 handler 可能会中止其他 handler，除非每个 handler 都被隔离。要决定失败的 reaction 应该阻塞其 sibling，还是只被局部隔离。
- **delivery semantics 是什么？** At-most-once（失败就 fire 并丢弃）、at-least-once（重试直到被确认，所以 consumers 可能看到重复）、还是 exactly-once（通常只是 transport 层的幻觉，借助幂等 consumers 加去重来近似）。大多数持久 broker 提供的是 at-least-once，这也是为什么 idempotency 不是可选项。
- **Poison messages 去哪儿？** 一个总是让 consumer 失败的 event 不能永远堵住队列。dead-letter queue 会把反复失败的 events 收集起来以供检查，而不是无限重试它们。

贯穿始终的原则是：对于 direct call，failure contract 是隐含而明显的；对于 events，你必须有意识地设计它，因为当事情出错时 producer 早就走开了。

## 与 Observer pattern 的关系

Observer pattern 是 event-driven design 在进程内最小的实例：subject 保存一组 observers，并在变更时通知它们。Event-driven architecture 将其泛化——“subject” 变成 event bus 或 broker，notification 变成 publish，observers 变成可能位于其他进程或服务中的 subscribers。依赖反转是一样的；区别在于 transport、durability，以及 delivery 是否同步。当地解耦是局部且同步时，普通 Observer（或一个简单的 callback list）就够了；只有在你需要跨进程投递、durability 或 async processing 时，才需要 broker。

## Events vs commands

有一个值得保持清晰的区分：`command` 是在告诉某个特定 handler 去做某事（`SendEmail`、`ChargeCard`），并期待它发生；`event` 是在宣布某件事已经发生（`OrderPaid`、`EmailSent`），并不要求谁来响应。Commands 是定向的，通常只有一个 handler；events 是广播的，可能有零个、一个或多个 handler。把两者混淆起来——把 event 命名得像 command，或者把已发布的 event 当成某个特定 consumer 必须处理的东西——会悄悄把 event-driven design 试图移除的 coupling 又带回来。用过去时态把 event 命名成事实；如果你开始在意*哪个* consumer 会运行，那你大概需要的是 direct call 或 command，而不是 event。

## 同步与异步投递

会改变整个 event system 性格的一个选择，是 `publish` 是在 handlers 完成前阻塞（同步），还是交出去后立即返回（异步）。同步的进程内投递比较容易推理——producer 的 call stack 仍然包含 handlers，exceptions 会向上传播，顺序也是确定的——但它把 producer 的 latency 和 failure 与 consumers 绑定在一起，这在某种程度上削弱了解耦。异步投递（队列、broker、background task）恢复了解耦，但也引入了所有分布式系统问题：at-least-once delivery、顺序、部分失败，以及对幂等 consumers 的需求。若 reaction 很便宜、局部，并且必须在 producer 继续之前完成，就选同步；若 reaction 很慢、远程，或与 producer 的成功真正独立，就选异步。

## 在 Python 中

- 进程内：一个简单的 `event_name -> list[callable]` 字典通常就够了；不要为了本地解耦就引入 message broker。

```python
from collections import defaultdict
from collections.abc import Callable

class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable) -> None:
        self._subscribers[event].append(handler)

    def publish(self, event: str, payload: object) -> None:
        for handler in self._subscribers[event]:
            handler(payload)   # producer never names a consumer
```

这就是这个模式在最小尺度下的全部样子：publisher 只知道 event 名和 payload，永远不知道 handlers。更大的系统——broker、durability、async delivery——只是同样的形状加上更多基础设施。

- Framework 通常会提供 signals/hooks（Django signals、Flask signals、pytest hooks）——在框架内部工作时，优先使用它自己的机制，而不是自己手搓一个。
- 把 event payload 设计成普通 data（`dataclass` / `TypedDict`），并使用稳定、带版本的 schema；这是 producer 与 consumer 之间的 contract。
- 让 consumer 具备 idempotency，并记录足够的 context（event ID、correlation ID）以追踪失败。
- 对于 async workflows，emit 出去的 event 通常会变成一个 task——见 [async-concurrency.md](./async-concurrency.md)，要关注这份工作的生命周期，而不是 fire-and-forget。
- 保持 audit 价值诚实：如果 events 是 source of truth，就要像对待 database schema 一样认真对待 event schema。
- 避免把本质上是 direct request-response 的流程做成 event。如果 producer 需要结果、会阻塞等待，或者只有一个 consumer，那么 plain function call 比 event round-trip 更清晰。
