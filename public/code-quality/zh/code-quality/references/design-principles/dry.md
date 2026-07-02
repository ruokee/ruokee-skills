# DRY — Don't Repeat Yourself

## 它是什么

DRY 是软件中最容易被误解的原则之一。它最初的表述（Hunt 和 Thomas，_The Pragmatic Programmer_）关注的是 _知识_：“系统中的每一份知识都应该只有一个清晰、无歧义、权威的表示。” 它不是“不能有两段代码长得像”。真正值得去重的是领域规则、schema、protocol、transform、错误处理 policy 这类决策——如果它变了，就必须同时在所有地方一起变。

DRY 警惕的危险，是同一份 knowledge 在多个地方出现，未来修改时可能有的地方改了、有的地方漏了。若某条税务规则、权限检查、状态迁移或校验条件散落在三个文件中，未来一次变更很容易漏掉其中一个，于是系统开始自相矛盾。

## 它背后的假设

- 同一份知识出现在多个地方时，未来的修改总会有些地方更新了、有些地方漏了。
- 单一权威表示可以让变更只发生在一个地方。
- 但看起来相似的代码，不一定表达同一份 knowledge。两段代码今天可能形状一样，却出于完全不同的原因，明天也可能由不同的力量驱动。

最后这一点区分了好的 DRY 和坏的 DRY。这个原则关心的是 knowledge，不是文本。

## 重复的知识 vs 偶然的相似

问自己：如果其中一份拷贝背后的需求变了，另一份是否 _也必须_ 一起变？如果是，它们编码的是同一份 knowledge——应当去重。如果不是，它们只是目前长得像——先别动。

真正的知识重复、值得去掉的例子：

- 同一条业务规则（价格计算、资格判断、状态机迁移）在多个地方实现。
- 一个 schema、API contract 或 data model 在 client、server 和 tests 中重复出现。
- 一个 retry 或 error-handling policy 在多个调用点被复制粘贴。
- 一条 data transformation 规则在多个函数中独立表达。

通常可以保留的偶然相似：

- 两个 validation function 恰好结构相同，但校验的是不同概念，而且未来会独立演化。
- 两个 request handler 共享平行的样板代码，但业务逻辑无关。
- 看起来重复的 test setup，但它们分别固定的是不同场景。

## 何时抽象，何时容忍重复

当重复的东西确实是一条规则，尤其是高风险知识时，应立即去重：安全、权限、金钱、protocol contract、数据一致性，以及任何 schema 的单一事实来源。对这些东西，不要等待——分叉的代价太高。参见 [rule-of-three.md](./rule-of-three.md) 关于例外结构的说明。

当两段内容只是形状相似，但由不同的变更原因驱动，且共享抽象的形状还不清楚时，就应容忍重复。过早统一会选错 seam。你从两个案例里提取出来的那个“generic” function，往往会随着第三、第四个案例到来而长出 boolean flag、mode 参数、callback、特殊分支和隐含前提——结果它比被替换掉的重复更难维护。这与 [kiss.md](./kiss.md) 直接形成张力：一个参数多、分支多的抽象，认知负担可能比两份清晰、分开的拷贝更大。

## 错误的 DRY

两种失败模式最常见，而且在 Agent 生成的代码里也很常见：

1. **过早抽象。** 在只看到两个偶然相似的片段时，就把它们统一起来，而 variation direction 还未知。结果变成一个参数怪物。当你发现这一点时，修复方式是：把抽象内联回去，让代码重新重复，再等待真实的 seam 自然浮现。

2. **参数化 / thin-wrapper 泛滥。** 为了“去重复”，把一两行抽成很多很小的 wrapper function。这几乎不会隐藏真实复杂度。它只会增加命名负担、跳转成本、更深的调用栈，以及——在 Python 中——真实的每次调用开销，因为每次调用都要创建一个 frame。把一个表达式换成近义词的 wrapper 只是 shallow helper，不是去重。关于如何识别和拆掉它们，见 `../refactoring/thin-wrapper-function.md`。

在提取 helper 之前，先问：它是否提供了稳定的 semantic boundary，是否隐藏了真实复杂度，或是否承载了可复用的 policy？如果唯一的答案只是“它被用了两次”，那还不是理由——那是 Rule of Three 要处理的事。

## 在 Python 中

- 优先去重 domain 概念、schema 和 protocol，而不是局部代码形状。
- 对重复的 schema/API/model 定义，使用单一事实来源：`dataclass`、`TypedDict`、Pydantic、OpenAPI spec，或代码生成。
- 对两个实现完全相同但业务原因不同的函数，先保留重复，直到 variation direction 变清楚。
- 比起为了共享代码而建立 class hierarchy，更应优先使用 module-level function、table-driven mapping、Protocol 和 strategy function。
- 表格和 dispatch map 是压缩真正重复知识的好方法（每个 case 一行），而不必引入 inheritance tree。

## 与其他原则的关系

- [rule-of-three.md](./rule-of-three.md) 是 DRY 的刹车：它会把形状相似代码的抽象推迟到第三个实例，同时仍允许立即去重已确认的知识。
- [deep-modules.md](./deep-modules.md)：把领域规则收束到一个清晰 interface 后，既满足 DRY，也满足 information hiding。
- [yagni.md](./yagni.md)：二者都反对 speculative structure，但 DRY 也可能推动抽象——让 YAGNI 和 Rule of Three 去约束它。
