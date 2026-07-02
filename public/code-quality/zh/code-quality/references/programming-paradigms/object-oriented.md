# Object-Oriented Programming

## 它是什么

Object-oriented programming 把 state、behavior 和 invariants 组织进 objects 中，并通过它们的协作来表达系统行为。一个 object 把 data 与被允许对这些 data 执行的 operations 绑定在一起，并且理想情况下确保 data 始终有效——其 invariants 在每个 public operation 中都成立。Python 完全支持 OO，但并不强迫你使用它：functions、modules 和 plain data 都是同等的一等替代方案。

OO 的价值在某个 concept 拥有长期 identity、需要保持一致的内部 state、并且有一组应当被放在一起的 operations 时最高。而当你只是在做一次性计算，或者只是把 data 从一种 shape տեղափոխ成另一种 shape 时，它的价值最低——在那里，用 function 或 plain record 更清楚。

## 其背后的假设

- 当一个 concept 拥有持久 identity、内部 state、invariants 和相关 behavior 时，把它建模成 object 能把保护这些 invariants 的 logic 放到一个地方。
- Object 的 interface 应该表达 _meaning_，而不是暴露它的内部 storage layout。
- Inheritance 只有在表示真正的 subtype relationship 或 framework extension point 时才有意义；如果只是想复用 implementation，composition 更合适。

## 何时适用

- Domain entities、value objects、resource objects、external clients、strategy objects、plugin objects。
- 必须维护 invariant 的 objects：state machine、money amount、time range、permission rule、bounded buffer。
- 有明显 lifecycle 的 objects：connection pool、transaction、cache、task runner。
- Polymorphism：在同一 interface 背后提供多个实现，并在 runtime 选择——不过在 Python 中，`Protocol` 加普通 functions 往往能用更少的 ceremony 表达同样的东西。

判断“这是不是应该是一个 object”的标准，是把 data 与其 operations 绑定起来是否 _保护了某个否则会落到所有人头上的 invariant_。一个拒绝把两种不同 currency 相加的 `Money` 类型，或者一个拒绝在 `end < start` 时构造的 `DateRange`，之所以值得成为 class，是因为这个保证只在一个地方存在，任何调用者都无法绕过它：

```python
@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("end must not precede start")

    def overlaps(self, other: "DateRange") -> bool:
        return self.start <= other.end and other.start <= self.end
```

系统里的每个 `DateRange` 都是按构造即有效的方式成立的，overlap 规则和它所操作的数据放在一起。相比之下，一个普通 dict `{"start": ..., "end": ...}` 的有效性则必须由每个调用者自行检查。

## 常见错误

- **Everything is a class.** 把简单的纯计算和 data transform 强行塞进没有 state 的 classes 里。一个由 functions 组成的 module 更清楚。
- **Anemic models.** `Manager`、`Service` 和 `Helper` 类吸走了所有 behavior，而“domain object” 只剩下一袋 public fields。data 与约束它的 rules 被拆开了——这恰恰和 OO 的目的相反。见 [../design-principles/tell-dont-ask.md](../design-principles/tell-dont-ask.md)。
- **Deep inheritance.** 为了复用 implementation 而不是替代 behavior 去做 subclassing。每增加一层都会增加 MRO complexity 和隐式 coupling。优先使用 composition；见 [../design-principles/composition-over-inheritance.md](../design-principles/composition-over-inheritance.md)。
- **移植自 Java/C++ 的 ceremony。** 为每次协作都引入 interface、abstract base class 和 factory layers，而在 Python 里本可以用 function、小型 `Protocol` 或 `dataclass` 来解决。

Anemic-model 的陷阱值得具体看一眼。贫血版本把规则分散到每个调用者：

```python
# Anemic: the rule "cannot withdraw more than balance" lives in callers
@dataclass
class Account:
    balance: int

def withdraw(account: Account, amount: int) -> None:
    if amount > account.balance:      # every caller must remember this
        raise ValueError("insufficient funds")
    account.balance -= amount
```

封装版本则由对象自己掌控规则，因此任何调用者都无法违反它：

```python
@dataclass
class Account:
    _balance: int

    def withdraw(self, amount: int) -> None:
        if amount > self._balance:
            raise ValueError("insufficient funds")
        self._balance -= amount
```

差别不只是风格。在第一种形式里，新的调用者如果忘了检查，就会破坏余额；在第二种形式里，不变量无法被绕过。这就是 [../design-principles/tell-dont-ask.md](../design-principles/tell-dont-ask.md) 原则的实践。

## Python 细节

- 简单 data carriers 使用 `@dataclass`；当存在真实不变量或需要管理 lifecycle 时，使用普通 class。见 [data-oriented.md](./data-oriented.md)。
- 对于跨边界的可替代性，优先使用小型 `typing.Protocol`（结构化类型），而不是名义上的基类。协作者只需要提供正确的方法。
- **data model**（dunder methods）是 object 与语言结合的方式：`__repr__`、`__eq__`、`__hash__` 用于 value objects；`__iter__`、`__len__`、`__contains__` 用于 containers；`__enter__`/`__exit__` 用于 resources；`__call__` 用于可调用的 strategies。只有当 object 确实具有这种语义时才实现这些方法——不要发明未文档化的 dunder。
- `property` 用于隐藏 storage 差异或暴露一个轻量的派生值，而不是隐藏 I/O、网络调用或 database query 之类的昂贵副作用。
- **Descriptors**（`property`、methods、ORM fields、validators 背后的 protocol）负责集中处理 attribute-access 行为。它们很强大，也很容易被过度使用；应把它们留在 framework/boundary code 中，而不是散落到业务逻辑里。对于普通字段验证，优先使用 `__post_init__`、Pydantic 或普通 constructor。
- 保持 mixins 小、无状态且命名清晰。Multiple inheritance 会很快把 MRO 变成隐式复杂度。

## 与其他 paradigms 的关系

一个有不变量的长期对象，通常最好配合 [state-machine.md](./state-machine.md) 来管理它的 lifecycle。它的方法内部的 decision logic 仍然可以是 pure 的，并向 [functional-core.md](./functional-core.md) 靠拢。“更 OO” 从来不是目标；目标是把 state、invariants 和 behavior 放在它们应在的边界上。
