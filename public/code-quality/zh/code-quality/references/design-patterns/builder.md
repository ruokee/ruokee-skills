# Builder

## 目的

把复杂对象的构造过程与最终表示分离开，这样同一个构造流程可以一步一步驱动、在过程中验证，或者复用来产出不同输出。

## 解决的问题

有些对象不适合用一次 `__init__` 调用就完成创建：可选参数太多、构造分阶段进行、输入来自多个来源，或者验证依赖字段组合。把这些全塞进 `__init__` 会产生很长的参数列表、望远镜式构造函数，以及与赋值纠缠在一起的验证逻辑。Builder 给组装过程单独起一个名字，便于测试和复用。

## 结构与参与者

经典形式里有一个 **director** 按步骤驱动一个 **builder** 接口；**concrete builder** 累积状态并产出一个 **product**。在实践中，director 往往会收缩成一个普通函数，而 builder 则是任何负责累积部分状态的东西。

## Python 形式

Python 很少需要完整的 fluent-builder 机械结构。通常下面几种更轻量的形式就够了：

- **带默认值的仅关键字参数** 直接处理“很多可选参数”：

    ```python
    @dataclass(kw_only=True)
    class Report:
        title: str
        sections: list[Section] = field(default_factory=list)
        summary: str | None = None
    ```

- **一个构造函数**（把“分阶段构造”作为一个命名阶段）把组装逻辑集中并保持可测试：

    ```python
    def build_report(config: ReportConfig, rows: Iterable[Row]) -> Report:
        sections = collect_sections(rows, config.section_rules)
        summary = summarize(sections, timezone=config.timezone)
        return Report(title=config.title, sections=sections, summary=summary)
    ```

- **kwargs 累积 / 逐步 dict**：当字段零散到达，最后由一次经过验证的构造调用收束。
- **fluent builder**（`builder.with_x(...).with_y(...).build()`）只在链式构造确实更清楚时使用，例如 query builder。

## 何时使用

- 对象有很多可选参数，或者有多种合法构造形态。
- 构造分多个阶段进行，并且阶段之间需要做中间验证。
- 同一个构造过程必须产生不同表示（HTML、PDF、JSON） - 这就是 Builder 的经典理由。
- 组装逻辑本身值得命名、测试并独立复用，而不只是 product 的附带过程。

## 何时不要用

- 一个普通 dataclass 配合关键字默认值已经说得很清楚了。给简单值对象再包一层 fluent builder，只是仪式感。
- 一个 Pydantic / msgspec model 已经能从原始数据做验证构造。
- builder 隐藏了一堆可变状态，调用顺序虽然重要却没有被强制 - 这比单个构造函数更难推理。

## 失效模式

- fluent builder 在 `build()` 之前就可能产出一个半初始化 product。要么在 `build()` 里校验，要么把必需字段做成构造参数。
- builder 状态被共享或在多个 product 之间复用，导致一次构造污染下一次构造。
- builder 复制了 product 自身的不变量，而不是委托给 product 自己的验证，导致二者逐渐偏离。

## 与其他模式的关系

[factory.md](factory.md) 一步决定“要造哪个类”；Builder 处理复杂的“如何组装”，而且分多个步骤。[abstract-factory.md](abstract-factory.md) 往往会用 builder 来构造它的各个 product。当你主要需要在已有模板上做小幅差异时，Prototype 方式（用 `dataclasses.replace` 从模板派生变体）是另一种选择，而不是全新的分阶段构造。
