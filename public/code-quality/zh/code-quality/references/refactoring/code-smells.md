# Code Smells

## 什么是 smell

code smell 是一个 **表面症状，提示可能存在更深层的结构问题** - 但它不是问题本身，也不是判决。Kent Beck 这个词故意借用了“异味”的比喻：它让你停下来仔细看一眼，但并不能证明一定有问题。一个长函数可能是问题，也可能只是清晰的线性流程。duplicated code 可能在三个地方编码了同一条规则，也可能只是三个今天看起来相似的片段。

这个区别 - 症状，而不是诊断 - 是 smell 最重要的地方。把 smell 当成自动缺陷，会导致机械式“修复”，反而把代码搞坏：对本不该拆分的函数进行提取，把并不是真重复的代码去重，为从未出现的变化引入抽象。smell 是一次调查邀请，而调查完全可能得出“这没问题”。

## 主要类别

Fowler 和 Beck 把 smells 分成几类。知道这些类别有助于你快速找到合适的修法。

- **Bloaters** - 代码长得太大，不便处理。Long Function、Large Class、Long Parameter List、Data Clumps、Primitive Obsession。它们往往是逐步累积出来的；每次新增看起来都合理，直到整体变得笨重。见 [long-function.md](./long-function.md) 和 [primitive-obsession.md](./primitive-obsession.md)。
- **Object-orientation abusers** - 对 OO 机制使用不完整或不正确。应当用多态的地方用了 Switch Statements、Refused Bequest、Temporary Field、Alternative Classes with Different Interfaces。
- **Change preventers** - 结构让一次改动不得不连带很多地方。Divergent Change（一个模块因为很多理由被改）和 Shotgun Surgery（一次改动散落到很多模块）是两个经典且相对的形态。见 [divergent-change.md](./divergent-change.md) 和 [shotgun-surgery.md](./shotgun-surgery.md)。
- **Dispensables** - 少了反而更清爽的东西。Duplicated Code、Dead Code、Speculative Generality、Lazy Element（一个没有真正贡献的 class 或 function - 与 thin wrapper 密切相关，见 [thin-wrapper-function.md](./thin-wrapper-function.md)）、用来解释糟糕代码的注释。见 [duplicated-code.md](./duplicated-code.md)。
- **Couplers** - 模块之间耦合过强的 smell。Feature Envy、Inappropriate Intimacy、Message Chains、Middle Man。见 [feature-envy.md](./feature-envy.md)。

这些类别会相互重叠，一段代码可能同时具备好几种。这个分类的目的在于帮助回忆 - 当感觉不对劲时，这些家族会提示你该如何命名你看到的东西。

## 如何分诊：现在值得修吗？

发现 smell 很容易。真正需要判断的是要不要动手，而答案经常是“现在先别”。可以快速分诊：

1. **它是被证实的问题，还是只是看起来像？** 先看表面下面的东西。重复的代码到底是不是同一条规则，还是两个只是长得像的片段？这个长函数是在混合抽象层次，还是只是一个清晰序列？如果你说不出底层结构问题是什么，就先停在这里。
2. **它挡住你了吗？** 在你正在改、或者马上要改的代码里的 smell 值得修 - 为后续改动做准备、提升理解的 refactoring 都会立刻回本。那些稳定、没人碰的代码，通常最好别动；改动工作代码的风险往往大于整洁收益。
3. **放着不管的代价是什么？** 高风险的知识重复（安全、金钱、协议契约、schema）即使只出现一次，也值得尽早修，因为分叉的代价很高。一个稍微长一点、但安静的角落函数，不值得。
4. **有安全网吗？** 如果你不能确认行为被保留，就先别重构。见 [safe-refactoring.md](./safe-refactoring.md)。

分诊的目标，是把重构精力花在能降低真实未来成本的地方，而不是把所有 smell 数量都清零。

## Agent 辅助开发中的 smells

Agentic coding 提高了代码生成速度，也加快了 smells 出现的速度。典型问题不是“代码看起来不像人写的”，而是结构性的：重复的 adapter、薄 wrapper helper、过宽的 Protocol、 speculative registry、深层 mock、同一条领域规则分别写在 schema、service 和 test fixture 里。因为产量更高，smell detection 也必须比传统手写代码更主动、更有意识 - 但上面的分诊原则更重要，因为真正的诱惑是机械地“清理”掉 agent 产出的所有东西。

## 与专门文档的关系

这篇文档是地图。这个目录里的每个叶子文档都深入讲一种 smell 或一种转换：它到底是什么、哪些信号能区分真问题和误报、什么时候这个 smell 其实可以接受、以及哪个命名 refactoring 负责处理它。分诊判断这个 smell 值得调查之后，就去对应的具体文档。具体转换 - Extract Function、Inline Function、Move Function - 分别在 [extract-function.md](./extract-function.md)、[inline-function.md](./inline-function.md) 和 [move-function.md](./move-function.md) 中，而安全应用这些方法的整体纪律则写在 [fowler-refactoring.md](./fowler-refactoring.md)。
