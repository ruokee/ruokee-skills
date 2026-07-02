# Test-Driven Development

Test-Driven Development（TDD）是一种由测试驱动开发反馈循环的工作流。你先列出一组 behavior，挑一个，写一个会失败的小型可运行测试，再写刚好足以让它通过的代码，然后再重构。Martin Fowler 把这个循环概括为 **Red-Green-Refactor**，并强调 refactor 步骤不是可有可无的装饰——它才是设计真正改善的地方。

TDD 首先不是测试技术，而是一种恰好会留下测试的设计技术。先写测试会迫使你在 interface 还不存在时就先使用它，这会更早暴露出别扭的 signature 和不清晰的职责。

## Red-Green-Refactor 循环

1. **Red。** 为一个小行为写测试，并让它失败。失败能证明测试确实触达了某些东西，而不是在悄悄通过。
2. **Green。** 写出最简单的代码，让测试通过。不是优雅版本，而是足够版本。这里允许走捷径；下一步会清理。
3. **Refactor。** 在测试已经通过并保护行为的前提下，改进结构：重命名、提取、去重复。整个过程中测试保持通过。

关键是每一步都要小，并且在每一步之间都运行测试。常见失败是把这个循环压扁：在一个测试下写一大批代码，或者把很大的结构性改动偷偷塞进 green 步骤里，而此时行为还没有稳定。

## TDD 带来的东西

- **设计反馈。** 先写测试意味着先消费 API 再实现它。令人痛苦的 setup、参数过多、难以构造的 collaborator，都会在测试中以痛感形式暴露出来，这本身就是设计信号。这与 [dependency-inversion](./dependency-inversion.md) 有关联：难以测试的代码，往往是因为它的 dependencies 没有被注入。
- **行为说明。** 测试套件会以可执行形式记录代码应该做什么，而且不会悄悄过时。
- **回归保护。** 一旦某个 behavior 被测试固定下来，未来破坏它的改动就会明确失败。这种保护使激进的 [refactoring](../refactoring/index.md) 和 [YAGNI](./yagni.md) 成为可能——你可以放心地推迟抽象并在之后重塑。

## 什么时候 TDD 有价值

TDD 最适合行为可枚举、且答错代价真实存在的场景：

- 纯函数、解析器、transform 和 serialization 逻辑。
- 有清晰输入输出的领域规则——定价、校验、状态迁移。
- 修 bug：先写能复现 bug 的失败测试，再修复。这个测试会成为永久回归防线。
- API 设计：先试着使用这个 interface，能更早看出它是否顺手。

## 什么时候严格 TDD 反而有害

TDD 假设你已经足够了解期望行为，能先写出测试。当你还没有时，严格的 test-first 会带来摩擦：

- **探索性代码和 spike。** 当 interface 甚至需求都还不清楚时，先写 spike 来学习，等形态稳定后再补 characterization 或 contract tests。此时强行 test-first，只是在测猜测。
- **UI 和视觉布局。** 这类价值很多来自外观和交互，而 unit test 很难捕捉。应该测试 UI 背后的逻辑，而不是像素位置。
- **Glue code。** 主要只是委托给已经充分测试过的 library 的薄 wiring，用一个测试去重复断言 library 的行为，收益很小。

把 TDD 看成一种高价值的反馈策略，而不是对每一行都必须遵守的道德义务。目标是获得能工作的、设计良好的软件以及足够的 behavior coverage，而不是 test-first 仪式感或 coverage 百分比奖杯。没有 meaningful assertion 的测试，只会增加 coverage，而没有别的价值。

## 与“事后测试”和 behavior coverage 的关系

在代码写完之后再补测试并不是罪过；关键是行为是否被覆盖，测试是否真的在断言某些东西。TDD 比 test-after 多出来的，是 red 步骤带来的设计压力。许多团队会混用两者：核心逻辑和 bug 修复用 TDD，探索性代码则事后补测试。两者都应该针对可观察行为，并选在合适的边界上，这样测试才能在重构后仍然有效。另见 [law-of-demeter](./law-of-demeter.md) 和 [dependency-inversion](./dependency-inversion.md)，它们解释了为什么深入内部去测（deep mock、patch 私有实现）的测试 smell 往往反映的是设计问题，而不只是测试问题。

## 在 Python 中

- `pytest` 很适合小步 TDD；保持 fixture 直接，不要围绕它们再搭一层隐形 framework。
- 对于 prototype、UI 和复杂外部集成，先 spike，再补 characterization 或 contract tests。
- `monkeypatch` 很方便，但也容易被滥用。优先在边界传入 fake 或 stub，而不是 patch 深层内部；必须 patch 很深，往往说明某个 dependency 本该被注入。
