# Grammar And Mechanism References

当 Python 语言构造是任务核心时阅读这些文件：决定是否使用它、评估已有用法，或解释它的行为。

- `match-case.md`：structural pattern matching（Python 3.10+）、其语法形式，以及何时优于或不如 `if`/`elif` 和 dispatch tables。
- `context-manager.md`：`with` / `async with` 协议、资源生命周期、基于生成器的 manager，以及 `__exit__` 中的异常处理。
- `decorator.md`：作为 higher-order functions 的 decorators、参数化和基于 class 的形式、metadata 保留，以及类型上的代价。
- `exception-groups.md`：`ExceptionGroup` 和 `except*`（Python 3.11+），用于并发和批处理失败，以及何时单个异常才是正确工具。

这些文档描述的是机制，不是评审政策。它们提供人或 agent 在评估具体用法时所需的上下文；评审工作流本身位于 `../../workflow/`。
