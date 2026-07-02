# Deep Modules and Information Hiding

本文借鉴 John Ousterhout 的 _A Philosophy of Software Design_。其核心思想是一种通过比较抽象接口成本与它隐藏的价值来判断抽象质量的方法。

## 深度：接口成本 vs 实现价值

每个 module 都有两个面：**interface**（调用方为了使用它必须理解的内容）和 **implementation**（接口背后的全部内容）。Ousterhout 将模块质量概括为二者之间的比值：

- **deep module** 的 interface 简单，却隐藏了大量有用的复杂性。调用方只需了解很少内容，就能获得很多能力。垃圾回收器、设计良好的文件系统 API，或者 `requests.get(url)` 都是 deep 的——调用简单，背后内容很重。
- **shallow module** 的 interface 几乎和实现一样复杂。调用方为了使用它，几乎要承担理解内部细节的全部成本，因此模块几乎没有净收益。一个只是在函数签名里重述自身 body 的一行 wrapper，就是极端例子。

模块的价值不在大小。deep module 在内部可以很大；关键是其 interface 相对于它吸收的复杂度要小。这重新定义了抽象的目标：不是“隐藏代码”，而是“让调用方忽略它不需要处理的复杂度”。

## 信息隐藏

深度背后的机制是 information hiding：每个 module 都封装一个设计决策——尤其是那些可能变化的，或很难做对的决策——这样其他 module 就不必依赖它。被隐藏的决策一旦变化，改动就能局部化。

与之相对的是 **information leakage**：某个设计决策同时出现在多个 module 中，于是一次变化就迫使多个地方都要修改。reader 和 writer 都知道的存储格式、每个 caller 都看得到的 wire protocol 细节、跨层重复的 error-mapping 约定——这些都是泄漏。泄漏是 [shotgun surgery](../refactoring/index.md) 等 smell 的更深层原因，而 information hiding 则是 [DRY](./dry.md) 在设计决策上的体现，而不仅仅是代码上的体现：知识只住在一个 module 中。

## 好抽象的特点

- 它隐藏的是确实值得隐藏的东西——一个困难算法、一个易变依赖、一个协议细节、一组错误和版本差异。
- 它的 interface 用的是调用方本来就在思考的术语，而不是实现术语。
- 它不会逼调用方记住正确的 _调用顺序_ 或内部状态才能正确使用。需要这种知识本身就是复杂度泄漏的一种形式。
- 常见情况调用简单；罕见情况仍然可用，但不会让常见路径变复杂。

一个常见的反模式是 **pass-through method**——一个方法除了用相同签名调用另一个方法外什么也不做。它增加了接口面和间接层，却什么也没隐藏，因此会让 module 更浅。对于只是把单个表达式换个名字的 thin wrapper function 也是一样：见 [DRY](./dry.md) 对 shallow helper 的讨论。

## 与 KISS 和 interface design 的关系

深模块让 [KISS](./kiss.md) 更有分量。“保持简单”并不意味着每个函数都必须短；它意味着尽量减少读者必须在脑中同时持有的复杂度。少数几个 interface 干净的 deep module，通常比一大堆迫使读者不断在文件之间跳转的 shallow helper 留下更少的总体复杂度。为了短函数和小文件而短，会制造 shallow module 和更多需要学习的 interface——这正好与 simple 相反。

深度也对 [Interface Segregation](./solid.md) 那种偏好小接口的冲动起到平衡作用：目标应当是“对它们所交付的东西而言足够小”的接口，而不是切得太薄以至于调用方为了完成任何事情都要拼装很多小接口。

## 原则被误用时

- 把 information hiding 理解成“每个 field 都设为 private，然后加 getter/setter”。机械暴露每个 field 的 accessor 什么也没隐藏，只是增加了 surface。对于简单数据载体，一个透明的 dataclass 完全没问题；只有在存在 invariants 或未来易变时才应封装。
- 隐藏调用方确实需要知道的内容——必要配置、有意义的错误，或真实的性能成本。隐藏成本并不会消除它，只会让调用方之后吃惊。
- 为了满足某种 file-size 或 function-length 偏好，把一个连贯的 deep module 切成很多 shallow 碎片。

## 在 Python 中

- Python 没有硬性的 `private`。应通过命名约定（`_internal`）、模块结构、`__all__`、明确的 public API、`property` 和 `Protocol` 来表达边界，而不是通过访问修饰符。
- 更倾向于让 module 的内部稍长一些，但局部清晰，也不要把逻辑散落到十几个读者必须追着跑的 shallow helper 里。
- Adapter 层天然就是一种 deep module：它把第三方 library 的细节隐藏在一个小接口后面，同时仍然暴露调用方必须考虑的错误和性能特征。这是 [anti-corruption layer](./ddd.md) 和 [Adapter](../design-patterns/adapter.md) 模式的结构基础。
