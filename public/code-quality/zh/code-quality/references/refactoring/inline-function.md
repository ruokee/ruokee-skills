# Inline Function

## 它是什么

Inline Function 是 [extract-function.md](./extract-function.md) 的反向操作：它用函数体替换一次调用，然后删除那个函数。Extract Function 是把概念提炼成名字；Inline Function 则是在名字不再值得保留时，把函数折回调用处 - 当函数体说得和调用一样多，甚至更清楚时，就该这么做。

```python
# before
def get_rating(driver):
    return 2 if more_than_five_late_deliveries(driver) else 1

def more_than_five_late_deliveries(driver):
    return driver.late_deliveries > 5

# after
def get_rating(driver):
    return 2 if driver.late_deliveries > 5 else 1
```

## 何时内联

- **误导性的名字。** 当函数名比函数体更不能准确描述内容时，这层间接反而在误导。内联可以去掉一个错误的路标。
- **纯转发。** 一个函数什么都不做，只是转发到另一个函数 - 也就是 [thin-wrapper-function.md](./thin-wrapper-function.md) 所说的 thin wrapper。当没有边界、没有测试 seam、后面也没有不稳定依赖时，就该内联。
- **函数体比调用更清楚。** 有时一个单行函数反而遮住了一个人人都懂的简单表达式。调用迫使读者跳过去确认一件显而易见的事；内联则让读者的视线停留在同一处。
- **逆转过早提取。** 早先的 refactoring（常常是 agent 生成的）沿着错误边界把代码拆成了很多小 helper。把它们内联回去几处，就能看见真正的形状，再按更好的边界重新提取。Fowler 的建议是：当间接层没帮助时，先内联，再重新提取。

## 内联前的安全检查

- **多态和重写。** 不要内联被子类重写的方法，也不要内联那些其动态分发本就有意义的方法 - 内联会把类型系统原本在选择的行为折掉。
- **递归和多个调用点。** 递归函数不能直接天真地内联。若调用者很多，把所有地方都内联可能是一次很大的变更；在动手前先想想这个函数是否真的物有所值，并考虑逐个调用点内联。
- **副作用和求值顺序。** 要确保把函数体折回去不会改变表达式的求值时机，尤其当参数有副作用或函数体读取可变共享状态时。
- **保留行为。** 和所有 refactoring 一样，每次内联后都要跑测试。见 [safe-refactoring.md](./safe-refactoring.md)。IDE 提供的 “Inline Method” 会处理机械替换并更新所有调用点。

## 何时不要内联

当函数提供的是一个围绕不稳定实现的稳定接口、作为测试 seam、命名了一个有助于搜索和理解的真实领域概念，或者隐藏了真实复杂度时，就保留它。短本身从来不是内联的理由 - 一个命名良好、边界清晰的小函数是好设计，不是 smell。问题始终在于名字和边界是否带来了意义，而不是它们后面到底有多少行。
