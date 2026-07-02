# Extract Function

## 它是什么

Extract Function 会把一段代码提取成自己独立命名的函数，并用一次函数调用替换原来的片段。它是最常见的 refactoring，也是 [long-function.md](./long-function.md) 的主要修法。Fowler 的指导原则是关于 _意图_ 的：如果你不得不花力气去弄明白一段代码在做什么，就把它提取成一个以 _what_ 命名的函数，而不是 _how_。这样名字承载意义，函数体承载机制。

```python
# before
def print_owing(invoice):
    outstanding = 0
    for order in invoice.orders:
        outstanding += order.amount
    print(f"name: {invoice.customer}")
    print(f"amount: {outstanding}")

# after
def print_owing(invoice):
    outstanding = calculate_outstanding(invoice)
    print_details(invoice, outstanding)
```

## 何时提取

- **一个连贯阶段。** 一段代码完成较大流程中的一个可辨识步骤 - 校验输入、计算总额、格式化输出。把每个阶段都提出来，长代码墙就会变成可读摘要。这和 Split Phase 很契合。
- **一个命名概念。** 一段具有领域含义的条件或计算：`is_overdue(invoice)` 比原始日期比较更好读，而且这个名字可被搜索。
- **一条策略。** 可能变化或会被复用的逻辑 - 评分规则、重试策略 - 适合被提成一个可以传递或替换的函数。见 `../design-patterns/` 里的 Strategy。
- **混合抽象层次。** 当高层意图和底层机制并排出现时，提取机制可以把调用方恢复到一致的层次。

## 给提取出来的函数命名

名字就是这次 refactoring 的核心。名字应当描述结果或意图 - `calculate_outstanding`，而不是 `loop_orders`。如果你找不到合适的名字，这就是一个信号：这段代码并不是一个连贯单元；要么你抓错了边界，要么在提取前就需要先重新思考这段代码。一个好名字会让调用点像句子一样自然。

## 参数决策

传入函数所需的东西，返回它产生的东西。优先保持参数列表短小。如果你发现自己总是在传一堆总是一起出现的值，那就是 Data Clump - 与其长签名，不如考虑引入一个小对象（见 `primitive-obsession.md`）。避免传一个 flag 让函数做两件事中的一件；这通常意味着一个函数里藏着两个函数。

## 保持行为不变

提取不能改变可观察行为。注意那些在片段内部被修改、且在后面还会使用的变量 - 它们要么变成返回值，要么说明边界本身就错了。注意那些在分离后不再有意义的早返回、`break` 和 `continue`。提取后要跑测试；见 [safe-refactoring.md](./safe-refactoring.md)。IDE 的“Extract Method”通常能机械而安全地处理大部分这些细节。

## 何时不要提取

- 代码已经在内联状态下很清楚，而且处在同一抽象层次。
- 提取会生成一个 [thin-wrapper-function.md](./thin-wrapper-function.md) - 一个名字只是复述单个表达式、只有一个调用方、没有边界的函数。
- 片段和周围状态纠缠太深，以至于提取出来的签名会有很多参数和很多返回值。先解缠，或者重新考虑这个边界。

提取是可逆的：如果后续阅读发现提取反而遮蔽了清晰度，就用 [inline-function.md](./inline-function.md) 把它折回去。
