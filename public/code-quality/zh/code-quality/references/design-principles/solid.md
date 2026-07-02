# SOLID

SOLID 是五条面向对象设计原则的集合——Single Responsibility、Open/Closed、Liskov Substitution、Interface Segregation、Dependency Inversion——由 Robert C. Martin 以 _dependency management_ 为主题整理而成。它们共同的目标是控制耦合以及变更方向，使系统在成长过程中依然保持灵活、稳健和可复用。

在讨论这些原则之前，先说两个框架。第一，应用单位不一定总是 class。这里的 “module” 可以是 function、module、package 或 service object——Python 通常不需要 Java SOLID 示例那种按概念切 class 的密度。第二，这些原则是 review 的 _问题_，不是模板。它们的价值在于问“这里会变什么、contract 是什么、dependency boundary 在哪里”，而不是机械地产生 interface 和 factory。把 SOLID 当模板用，往往会得到 class explosion 和违反 [kiss.md](./kiss.md) 的间接层。

## Single Responsibility Principle

SRP 通常表述为“一个 module 只有一个变更原因”。这里的 reason-to-change 比常见误读“一个 class 只做一件事”更重要。一个 responsibility 对应的是一个 _变更来源_——一个 actor、一个 stakeholder、或一条独立演化的规则。合适的粒度来自 cohesion，而不是来自尽量减少单元做的事情数量。

SRP 要捕捉的 smell 是：一个 module 把业务规则、展示格式化、持久化和外部 API 适配混在一起，于是任何一项变化都可能牵连其他部分。人们在应用 SRP 时常犯的错误是：把一个本来内聚的对象拆成很多贫血 helper，逻辑被四处分散，内聚反而下降。要问的是“这段代码是否回应了不止一种规则、角色或外部系统？”——而不是“这个 function 是否做了超过一个小事情？”在入口点，解析、配置、日志和依赖装配可以放在一起；业务规则应该移到 core。

## Open/Closed Principle

OCP：一个稳定的 core 应该对扩展开放、对修改关闭——也就是通过添加新的 implementation、strategy 或 config 来增加行为，而不是每次都回到 core 里改它。现代、务实的解读有一个前提：只有当 variation 的方向稳定且确实会重复出现时，建立扩展点才值得。

这使 OCP 与 [yagni.md](./yagni.md) 直接形成张力。为一个假想中的第二个 implementation 构建 plugin architecture，就是 speculative generality。解决方式是：先用一个简单的 branch 或 mapping；只有在真实的第二个（最好是第三个——见 [rule-of-three.md](./rule-of-three.md)）variation 出现后，再引入 registry、dispatch table 或 Protocol。在 Python 中，扩展机制通常是 registry、entry points、config-to-function mapping、`Protocol`、decorator 或 strategy function——不一定非得是 inheritance hierarchy，因为那通常会产生 fragile base class。

## Liskov Substitution Principle

LSP：subtype 必须可以在任何期待 base type 的地方使用，而不会破坏程序的预期。关键字是 _behavior_，不是 signature。方法名和类型一致是必要条件，但还不够；subtype 还必须遵守 base 的 precondition（不能更苛刻）、postcondition（不能少承诺）、invariants 以及 exception semantics。

经典违规：subclass 缩小了方法能接受的输入，或者把继承来的 method 改成 no-op 或 `raise NotImplementedError`，或者仅仅为了复用代码而 subclassing，但根本没有真实的 _is-a_ 关系。在 Python 中，duck typing 和 `Protocol` 只表达结构——behavioral contract 仍然活在 tests 和文档里。当你只是想复用实现时，优先使用 composition、小型 mixin 或 helper function，而不是 inheritance，这样你就不会做出自己无法兑现的 substitutability 承诺（见 [composition-over-inheritance.md](./composition-over-inheritance.md)）。

## Interface Segregation Principle

ISP：不能强迫 client 依赖它们根本不用的方法。过宽的 “god interface” 会把每个 client 绑到每次变化上，还会迫使 test double 实现无关方法。应当按照真实 caller 实际需要的内容来拆分 interface。

在 Python 中，这很少意味着 Java 式的 interface class。更常见的是使用小的 `Protocol`、普通 callable、module-level function，或者一个只携带 caller 需要能力的参数对象。不要为了一个函数硬造一个 interface；一个内部的一次性调用不需要声明式 interface——让函数只接收它真正使用的对象即可。一个好经验是：当 test double 需要 stub 代码根本不会调用的方法时，这个 interface 就太宽了。

## Dependency Inversion Principle

DIP：高层 policy 不应依赖低层 detail；二者都依赖 abstraction，而这个 abstraction 由高层代码需要什么来定义（而不是从 detail 中泄漏上来）。这能让业务规则摆脱数据库、HTTP、文件系统、时钟、随机数以及 framework 细节。Dependency Injection 只是实现 DIP 的一种 _技术_——把 dependency 从外部传入，而不是在内部构造或查找。完整讨论见 [dependency-inversion.md](./dependency-inversion.md)。

常见错误是把 DIP 等同于 DI container，或者把稳定的标准库代码也反转掉，仿佛它们将来会需要替换。在 Python 中，应优先使用 constructor parameters、function parameters、小 `Protocol` 和 factory function，并在 composition root（`main()`、app 启动、framework entry）中装配具体依赖。

## SOLID 的张力与过度使用

每条原则都在推动更多结构——更多 interface、更多间接层、更多注入点。如果不加判断地应用这一整套，就会得到 [kiss.md](./kiss.md) 和 [yagni.md](./yagni.md) 所警惕的那种过度设计、难以阅读的代码。具体张力包括：OCP vs YAGNI（扩展点 vs 投机）、ISP vs 简单性（接口数量）、DIP vs 简单 wiring（间接性 vs 可追踪性）。应当在变更频繁且代价高的地方使用 SOLID——长期存在的业务系统、库、framework、SDK、plugin point——而把小脚本和稳定 module 放在一边。把 SOLID 当成一组关于变更与耦合的 review 问题，让 Python 的 function、Protocol、composition 和参数注入成为默认答案，而不是 ABC 和 container。
