# Refactoring

这是 Martin Fowler 式 refactoring 的参考文档：由 code smells 驱动、且保持行为不变的结构调整。目标不是“为了整洁而整洁”，而是一种有纪律的实践 - 识别症状、保护当前行为、再做小而命名清晰、可逆的变换。这个目录里既有框架文档，也有 smell 目录，还有最常在日常工作和 agent 辅助工作中遇到的 smell 与 refactoring 叶子文档。

如果你是在判断 _要不要_、以及 _怎么_ 重构，就先看框架。如果你已经看到了某个症状，想弄懂它以及它的修法，就去对应的 smell 文档。如果你已经知道自己要做什么变换，就去具体的 refactoring 文档。

## 框架

|问题|阅读|
|-|-|
|什么是 refactoring，什么时候该做，什么时候不该做|[fowler-refactoring.md](./fowler-refactoring.md)|
|什么是 code smell，属于哪一类，现在值不值得修|[code-smells.md](./code-smells.md)|
|如何在不破坏行为的情况下重构|[safe-refactoring.md](./safe-refactoring.md)|

## Smells

|症状|阅读|
|-|-|
|函数做得太多，混了抽象层次，难命名|[long-function.md](./long-function.md)|
|同一份知识在多个地方表达|[duplicated-code.md](./duplicated-code.md)|
|该用领域类型时却用了字符串 / 整数 / dict|[primitive-obsession.md](./primitive-obsession.md)|
|某方法比起自己更常用别的对象的数据|[feature-envy.md](./feature-envy.md)|
|一次逻辑改动要改很多地方|[shotgun-surgery.md](./shotgun-surgery.md)|
|一个模块因为很多不相关的原因而变化|[divergent-change.md](./divergent-change.md)|
|函数只是转发调用或改名，没有增加价值|[thin-wrapper-function.md](./thin-wrapper-function.md)|

## Refactorings

|变换|阅读|
|-|-|
|把一个连贯片段提成独立命名函数|[extract-function.md](./extract-function.md)|
|把函数折回调用方|[inline-function.md](./inline-function.md)|
|把行为迁移到更合适的拥有者|[move-function.md](./move-function.md)|

Smells 和 refactorings 是同一实践的两面：smell 命名问题，refactoring 命名解法。smell 文档会指向能解决它们的 refactoring，而 refactoring 文档也会说明它们针对的是哪些 smell。关于这些判断背后的原则 - DRY、Rule of Three、single responsibility - 见 `../design-principles/`。
