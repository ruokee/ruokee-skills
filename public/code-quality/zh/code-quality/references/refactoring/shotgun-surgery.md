# Shotgun Surgery

## 它是什么

Shotgun Surgery 指的是这样一种 smell：一个概念性的改动迫使你在很多不同的文件或 class 里做很多很小的修改。你决定增加一种新的支付方式、改变日期格式，或者重命名 wire protocol 里的一个字段 - 突然就要碰十几个模块，每个模块都只改一点点。漏掉任何一个，系统就会微妙地坏掉。逻辑上是一次改动，物理上却散得满天飞。

这种痛是在修改时感受到的，这也是它之所以是 _change preventer_ 的原因：单看某一个地方，代码也许挺好读，但演化它的成本很高，而且总有漏改的风险。一个决定被涂抹到的地方越多，未来某次编辑只改了大部分却忘了剩下那一小部分的概率就越高。

## 信号

当一次常规改动在一堆看似无关的文件里引发一长串重复 diff 时，或者你脑中的检查清单变成“别忘了也改 X、Y、Z”时，你就会注意到它。代码评审里那些“验证器 / 序列化器 / 文档也改了吗？”之类的问题，就是社会层面的信号。一种实用的检测方式是：直接做这次改动，看看编辑是怎么散出去的 - 如果一个职责需要改七个地方，那这七个地方其实都在持有同一个概念的碎片。

这通常是 Primitive Obsession 和 Duplicated Knowledge 的下游结果：当一个领域概念（状态、费率、格式）没有单一归宿时，每个使用它的地方都必须编码同样的知识，所以对这条知识的每次变更都会打到每个地方。见 [duplicated-code.md](./duplicated-code.md) 和 [primitive-obsession.md](./primitive-obsession.md)。

## 它在告诉你什么

Shotgun Surgery 是在提示 **缺少抽象** 或 **凝聚性差**：本该只在一处出现的东西被拆散到了很多地方。修法是把这些散落的碎片收拢到一个单独的 module、class 或 function 里，由它来拥有那个决定 - 这正好和这个 smell 相反。常见动作包括：

- [move-function.md](./move-function.md) 和 Move Field，把分散的行为和数据收拢到一个拥有者手里。
- 引入缺失的类型（value object、enum、config object），让这个概念有自己的家，这样分散的用法就会坍缩成对这个类型的引用。
- 用单一事实来源替换重复知识 - 一个表、一个 dispatch map、一个 schema - 让一次变更只对应一处编辑。

目标是让未来同类变更只碰一个地方。你不一定总能做到绝对“一处”，但从十二处降到两处，风险就已经大幅下降了。

## 与 Divergent Change 的关系

Shotgun Surgery 和 [divergent-change.md](./divergent-change.md) 是互为反面的 smell，值得放在一起看，因为它们的修法方向正相反。

- **Shotgun Surgery：** _一次改动 → 很多模块。_ 一种变化被分散到太多地方。修法是 **收拢** - 把碎片收回来，让变化局部化。
- **Divergent Change：** _一个模块 → 很多种变化。_ 一个模块因为很多不相关的理由而变化。修法是 **拆分** - 分离职责，让每个职责只因一种理由变化。

两者都在说：模块边界要跟代码实际变化的轴对齐。Shotgun Surgery 说明边界缺失了（一个概念没有家）；Divergent Change 说明边界放错了（一个模块装了太多概念）。它们共同指向的目标就是 Single Responsibility Principle，读作“一个修改理由” - 见 [../design-principles/solid.md](../design-principles/solid.md)。修一个有时会暴露另一个，所以每次移动后都要重新评估，别在一次 pass 里过度收拢或过度拆分。
