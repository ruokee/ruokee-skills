# Data-Oriented Design

## 它是什么

Data-oriented design 从 data 出发，而不是从 behavior 出发。它不问“有哪些 objects，它们能做什么”，而是问“data 的形状是什么，它如何在系统中流动，它经历了哪些 transformations”。你会优先使用的结构很朴素：schemas、tables、records、typed dicts、仅作为 data 使用的 dataclasses，仅此而已。Behavior 放在接收 data 并返回 data 的 functions 里，而不是绑定在 data 上的 methods 里。

在它的起源场景（game engines、高性能系统）里，这个术语带有很强的关于 memory layout 和 cache locality 的主张。在普通应用代码里，更实用、也更克制的理解是：显式建模 data，并让它的形状驱动程序结构。大多数 ETL jobs、API 边界、configuration systems 和 batch processors 本质上都是 data pipelines，把它们写成这样会最清楚。

## 其背后的假设

- Data 有一个形状，而且这个形状通常是程序里最稳定的东西之一。endpoints、rules 和 UIs 往往比核心 record 变化得更频繁。
- 将 data（惰性的结构）与 behavior（对它做运算的 functions）分离，会让两者都更容易检查、序列化、版本化和测试。
- 对于 pipeline 型问题，“这个 data 会经过哪些 transformations” 比“哪些 objects 彼此协作” 是更诚实的拆分方式。

## 何时适用

- **ETL 和 data pipelines。** Records 依次经过 parse、validate、transform、aggregate 和 write 各阶段。每一阶段都是 data 到 data 的函数；这既是 data-oriented design，也是 [functional-core.md](./functional-core.md) 从两个角度描述同一个系统。
- **API 边界。** Request 和 response bodies 都是 data。把它们建模成 schemas（dataclass、TypedDict、Pydantic），并让 handler logic 作为对这些 data 的 transformations。
- **Configuration。** Config 是声明式 data（见 [declarative.md](./declarative.md)）；在边界处把它解析成 typed structure，然后向内传递这个结构。
- **Batch processing。** 每条 record 的规则是作用于普通 record 的纯函数；外层循环、checkpointing 和 I/O 则属于 imperative shell。

## 与 functional style 的关系

Data-oriented design 和 functional programming 是密切的盟友。Functional style 说的是“优先使用 pure functions，而不是围着 data 做文章”；data-oriented design 说的是“把 data 显式化，并让它领路”。两者合在一起会得到相同的架构：近似不可变的 records 在 pure transformations 之间流动，副作用被推到边缘。区别只在强调点上：一个从 functions 出发，另一个从 record 的形状出发；在实践中它们会汇合。

## 什么时候对象更合适

当 data 带有必须始终成立的不变量时，data-oriented 立场就会明显变弱。普通 record 是惰性的：没有任何东西会阻止调用者把它放进非法组合。若某个概念对哪些字段组合有效、生命周期、或必须与自身状态保持一致的 behavior 有规则，那么用一个把该状态封装起来并保护不变量的 object 更合适。见 [object-oriented.md](./object-oriented.md)。

你已经把 plain data 推得太远的迹象包括：

- 同一个 record 的 validation logic 被复制粘贴到每个触碰它的 function 里，因为没有任何单一位置拥有这个不变量。
- 调用者可以构造出本不应可能的字段组合（[state-machine.md](./state-machine.md) 所说的 “boolean flag soup” smell）。
- 这个“data”开始长出很多不同 functions 需要共享并保持一致的 behavior。

到那时就该封装了。Plain data 适用于其有效性由产生它的边界来保证的 records；objects 则适用于其有效性必须持续维护的 concepts。

## 一个具体的形状

一个 data-oriented pipeline 会表现为一串对显式 records 的 transformations，每一阶段都是从 data 到 data 的 pure function：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RawRow:
    name: str
    amount: str


@dataclass(frozen=True)
class Charge:
    name: str
    cents: int


def parse(row: RawRow) -> Charge:
    return Charge(name=row.name.strip(), cents=round(float(row.amount) * 100))


def charges(rows: list[RawRow]) -> list[Charge]:
    return [parse(r) for r in rows]
```

这些 records 不携带 behavior；这些 functions 不携带 state。读取、写入和 checkpointing 发生在外围的 imperative shell 中，而不是这些函数里。正是这种分离，让每一阶段都能用字面 data 测试，并组合成更长的 pipeline。

## 让非法 data 难以表示

认真对待 data 还有一个更安静的好处：一个设计得好的 shape 可以在任何 logic 运行之前就消除一整类 bug。如果一个 field 只能是三个值之一，就把它建模成 enum，而不是自由字符串。如果两个 field 必须同时出现或者同时缺失，就把它们放进一个嵌套 record，而不是两个独立 optional。如果一个 list 必须非空，那就值得在边界处编码或检查一次。原则就是把 validity 推进 data 的 shape 中，使下游 functions 可以信任输入，而不必反复检查。这和 [state-machine.md](./state-machine.md) 里拒绝让 boolean flags 充当 state 的直觉是一样的：type 是第一道防线。

这件事应当发生在边界。把不可信输入（JSON、config、request bodies）一次性解析成 typed structure，并在过程中完成验证，然后让内部所有东西都在可信的 shape 上运行。这就是“parse, don't validate”：把原始 data 转成一种其存在本身就保证有效性的结构，而不是把原始 data 传播得到处都是，再到处散布 validation checks。

## 在 Python 中

- 对纯 data record 优先使用 `dataclass`；当 record 是没有 identity 的 value object 时，优先考虑 `frozen=True`（参见 stdlib references 中关于 dataclass 的说明）。
- 当 data 以 dict 形式到达（JSON、config）且你希望在不转成 object 的情况下做 shape-checking 时，使用 `TypedDict`。
- 把这些结构保持为 data：避免给 dataclass 挂重型 business workflow。那会变成“无意中贫血，然后又被过度塞满”的 antipattern。如果真的出现不变量，就升级成带 methods 的 class。
- 对每个 schema 建立单一事实来源，而不是在 types、runtime validation 和 docs 中重复声明同一个 shape。
- Transformations 应该放在 module-level functions 中，它们作用于 data，并可组合成 pipelines；除非行为本质上属于该 type，否则不要放进 methods 里。
