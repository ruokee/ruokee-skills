---
name: code-quality
description: General code quality review and design guidance covering design principles, design patterns, refactoring, programming paradigms, code smells, state machines, resource lifecycle, abstraction quality, and Agent/Skill configuration smells. Use when asked to evaluate code quality, design tradeoffs, refactoring opportunities, paradigm fit, abstraction boundaries, or AGENTS.md/SKILL.md/configuration quality.
---

# Code Quality

在需要判断代码、架构、重构计划、抽象、设计原则、设计模式、编程范式以及 Agent 配置是否具备合理结构、变更边界和维护成本时，使用这个 Skill。

对于 Python 代码 review 或日常 Python 自检，若用户没有明确缩小范围，也一并使用 `python-engineering`。

## 进入条件

当任务涉及可维护性、设计质量、抽象边界、重构、code smells、编程范式选择、设计模式使用、设计原则或 Agent/Skill 配置质量时启用此 Skill。参考叶子文档涵盖设计原则、设计模式、重构、编程范式与 agentic-coding；按信号加载，而不是全部读取。

## 模式选择

可用三种模式。默认使用快速 review。

|模式|触发条件|读取|
|-|-|-|
|快速 review|日常自检默认、小 diff、PR review|`workflow/fast-review.md`|
|完整 review|用户明确说 “full review”、“architecture review”、“systematic review”、“refactoring assessment”|`workflow/full-review.md`|
|分析|用户在讨论、头脑风暴、设计探索、范式比较、机制分析|`workflow/analysis.md`|

## 判断顺序

1. 识别主要关注点：正确性、可读性、变更成本、可测试性、性能或交付成本。
2. 判断问题属于原则、模式、重构、范式还是 Agent 配置。
3. 路由到下方对应的叶子文档。
4. 只报告证据充分的问题。

|信号|先读|常配合|
|-|-|-|
|DRY、重复知识、错误抽象|[DRY](references/design-principles/dry.md)|Rule of Three, duplicated code|
|两个相似案例、过早抽象|[Rule of Three](references/design-principles/rule-of-three.md)|DRY, KISS|
|不必要的复杂度|[KISS](references/design-principles/kiss.md)|YAGNI, deep modules|
|过早的扩展点、不需要的灵活性|[YAGNI](references/design-principles/yagni.md)|KISS, deep modules|
|SOLID、职责、可替换性、接口宽度、依赖方向|[SOLID](references/design-principles/solid.md)|composition over inheritance, dependency inversion|
|职责分配、行为应该放在哪里|[GRASP](references/design-principles/grasp.md)|Tell Don't Ask, feature envy|
|消息链、远距离对象结构知识|[Law of Demeter](references/design-principles/law-of-demeter.md)|deep modules, facade|
|调用方先查询字段再做领域决策|[Tell Don't Ask](references/design-principles/tell-dont-ask.md)|GRASP, feature envy|
|继承 vs composition、mixins、为复用而 subclassing|[Composition over Inheritance](references/design-principles/composition-over-inheritance.md)|SOLID, dependency inversion|
|dependency inversion、DI、composition root|[Dependency Inversion](references/design-principles/dependency-inversion.md)|adapter, repository, unit of work|
|TDD、Red-Green-Refactor、behavior-first tests|[TDD](references/design-principles/tdd.md)|safe refactoring|
|Domain-driven design、bounded contexts、domain modeling|[DDD](references/design-principles/ddd.md)|deep modules, repository|
|抽象深度、information hiding、shallow modules|[Deep Modules](references/design-principles/deep-modules.md)|KISS, facade|
|对象创建会随类型/配置/环境变化|[Factory](references/design-patterns/factory.md)|abstract factory, builder|
|成套产品家族一起变化|[Abstract Factory](references/design-patterns/abstract-factory.md)|factory, builder|
|复杂的分阶段构建|[Builder](references/design-patterns/builder.md)|factory, abstract factory|
|算法/行为在稳定调用点后变化|[Strategy](references/design-patterns/strategy.md)|factory, functional core|
|一个事件通知多个订阅者|[Observer](references/design-patterns/observer.md)|event-driven, command|
|外部接口需要翻译|[Adapter](references/design-patterns/adapter.md)|facade, dependency inversion|
|跨切关注点包装调用/对象|[Decorator](references/design-patterns/decorator.md)|facade, thin wrapper function|
|简单表面之下隐藏复杂子系统|[Facade](references/design-patterns/facade.md)|deep modules, adapter|
|请求被排队、重试、审计、撤销、调度|[Command](references/design-patterns/command.md)|state, observer|
|state-specific behavior，GoF State Pattern|[State](references/design-patterns/state.md)|state machine, command|
|在稳定节点类型（AST/tree/schema）上变化的操作|[Visitor](references/design-patterns/visitor.md)|strategy|
|持久化边界、ORM 隔离|[Repository](references/design-patterns/repository.md)|unit of work, dependency inversion|
|repositories 之间的 transaction/consistency|[Unit of Work](references/design-patterns/unit-of-work.md)|repository, dependency inversion|
|作为保持行为不变的 Fowler 风格工作来理解重构|[Fowler Refactoring](references/refactoring/fowler-refactoring.md)|safe refactoring, code smells|
|一般的 smell 分诊和 smell map|[Code Smells](references/refactoring/code-smells.md)|具体重构叶子文档|
|安全的保持行为不变的重构流程|[Safe Refactoring](references/refactoring/safe-refactoring.md)|fowler refactoring, TDD|
|函数混合了阶段、policy、I/O、分支|[Long Function](references/refactoring/long-function.md)|extract function, duplicated code|
|重复的规则、映射、schema、复制的知识|[Duplicated Code](references/refactoring/duplicated-code.md)|DRY, extract function|
|字符串/dict/primitive 承载稳定的领域含义|[Primitive Obsession](references/refactoring/primitive-obsession.md)|DDD, data-oriented|
|函数羡慕另一个对象/module 的数据|[Feature Envy](references/refactoring/feature-envy.md)|move function, GRASP|
|一次变更需要很多分散修改|[Shotgun Surgery](references/refactoring/shotgun-surgery.md)|divergent change, move function|
|一个模块因许多无关原因而变化|[Divergent Change](references/refactoring/divergent-change.md)|shotgun surgery|
|helper/wrapper 没有增加语义边界|[Thin Wrapper Function](references/refactoring/thin-wrapper-function.md)|KISS, facade|
|将一个连贯阶段提取为函数|[Extract Function](references/refactoring/extract-function.md)|long function, inline function|
|内联一个误导性或过浅的函数|[Inline Function](references/refactoring/inline-function.md)|extract function|
|将行为移动到更合适的 owner|[Move Function](references/refactoring/move-function.md)|feature envy, GRASP|
|直接步骤、脚本、handlers、编排|[Imperative](references/programming-paradigms/imperative.md)|declarative|
|配置、schema、table-driven、声明式|[Declarative](references/programming-paradigms/declarative.md)|imperative|
|对象 identity、state、invariants、polymorphism|[Object-Oriented](references/programming-paradigms/object-oriented.md)|composition over inheritance, SOLID|
|将纯逻辑与有副作用的 shell 分离|[Functional Core](references/programming-paradigms/functional-core.md)|strategy, declarative|
|显式数据形状、映射、schema、tables|[Data-Oriented](references/programming-paradigms/data-oriented.md)|primitive obsession, declarative|
|events、hooks、event bus、pub/sub、domain events|[Event-Driven](references/programming-paradigms/event-driven.md)|observer, command|
|状态/状态码/事件/迁移工作流|[State Machine](references/programming-paradigms/state-machine.md)|state, resource lifecycle|
|资源获取、所有权、清理|[Resource Lifecycle](references/programming-paradigms/resource-lifecycle.md)|state machine, unit of work|
|async tasks、cancellation、timeouts、backpressure|[Async/Concurrency](references/programming-paradigms/async-concurrency.md)|event-driven, resource lifecycle|
|AGENTS.md、SKILL.md、prompt/rules/workflow config|[Config Smells](references/agentic-coding/config-smells.md)|DRY, KISS|

`index.md` 文件用于人工导航。只有在目录边界本身不清楚时才读取对应的 `index.md`。

## 偏好

在识别出相关叶子文档后，再读取项目事实和可选偏好：

1. 先读最近的可用 `AGENTS.md` 或项目规则。
2. 读取项目代码、测试、配置以及与 review 相关的 diff。
3. 通过启发式方式寻找偏好：
    - 先尝试项目级：`.agents/preferences/code-quality.md`，然后 `.agents/preferences/code-quality/index.md`。
    - 如果不存在，再尝试用户级目录：`~/.codex/preferences/code-quality.md`、`~/.claude/preferences/code-quality.md`，或等价的用户配置目录。
4. 如果任何层级都没有找到偏好，就静默继续。

偏好可以规定：review 优先级、架构约束、项目特定 smell，或额外规则。不要把偏好当作普遍工程真理来表述。

## 输出契约

先给结论。原则不是机械规则，要写取舍；模式不是默认模板，必须先证明 variation point 真实存在。把事实、推断、判断、偏好和建议分开，不要混在一起。不要重复 formatter 或 linter 可以机械捕捉的问题。

输出格式按模式而定——遵循对应的 workflow 文档（`workflow/fast-review.md`、`workflow/full-review.md` 或 `workflow/analysis.md`）。分析模式给取舍和选项，而不是 findings 列表。

输出语言遵循全局/项目/用户指令；未明确指定时，使用当前对话的语言。

## 停止规则

- 不要为了满足某个原则而硬找问题。
- 不要仅因为代码看起来相似就抽象。
- 不要仅因为两个地方都像就把它们当作重复知识，必须证明它们共享同一意图。
- 不要自动应用重构、补丁、不安全修复或批量抑制。
- 不要把偏好当作普遍工程真理。
- 在 read-only 或 analysis 任务中不要写文件修改。
- 不要报告 formatter 或 linter 可以机械捕捉的问题——如有必要只提一次，然后继续。
