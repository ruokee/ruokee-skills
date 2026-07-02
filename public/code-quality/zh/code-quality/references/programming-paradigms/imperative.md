# Imperative / Procedural Programming

## 它是什么

Imperative programming 把计算描述为一系列改变 state 的 statements：读取输入、修改变量、调用外部系统、处理错误、写出输出。Procedural programming 则是把同一个模型组织成按顺序调用的 procedures（functions）。这是最古老、也最直接的程序表达方式，并且与机器实际执行方式非常接近。

把 imperative code 轻易看低，视为低级或不够高级，是一种错误。现实世界本来就充满有序的副作用——打开文件、读取、转换内容、写回、提交 transaction——而 imperative style 是表达这种序列最诚实、最清晰的方式。目标不是消灭 imperative code，而是把它放回它应在的位置，并阻止 business rules 与它缠在一起。

## 其背后的假设

- 有些 logic 天生就是 sequential 的：每一步都依赖上一步的 effect。
- 副作用应该是 _可见的_，按顺序展开，而不是藏在层层抽象之后。
- 对于短脚本、entry points 和 wiring layers，直接的线性流程通常比过早的架构更易维护。

## 何时适用

- CLI entry points、一次性脚本、migrations、operational tooling。
- Application startup：dependency wiring、config loading、logger initialization。
- I/O orchestration：协调 transaction、按要求顺序调用多个外部系统、安排 reads 和 writes 的先后。
- 几乎任何程序的外层——也就是那些真正要在世界里 _做事_ 的部分。

一个健康的 imperative entry point 会像 recipe 一样易读——每一步都命名了一个阶段，而且副作用按顺序显现：

```python
def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config_path)
    configure_logging(config.log_level)
    client = build_client(config)
    try:
        result = run_job(client, config)  # decision logic lives here, takes plain data
    except JobError as exc:
        logging.getLogger(__name__).error("job failed: %s", exc)
        return 1
    write_report(result, args.output)
    return 0
```

注意这个 entry point _没有_ 做什么：它没有自己计算结果。它只是安排 I/O，并把实际 decision 交给 `run_job`，后者可以在没有真实 client 的情况下被测试。

## 什么时候会变成问题

- Core business rules 与 I/O 被交织在一个长函数里，导致你无法在不依赖 database、clock 或 network 的情况下测试规则。
- 复杂的 state changes 没有边界，并通过 globals 或一个到处传递的 mutable dict 泄漏到每一层。
- Error handling 分散在流程各处，既无法复用，也难以作为一个整体推理。
- Function 已经长到超出读者脑中可容纳的程度，而唯一的结构就是从上到下的顺序。
- “再加一个 flag” 的参数越来越多，最终把 procedure 变成由十几个 booleans 共同驱动隐藏分支的机器——这是不同于单纯顺序的另一类信号：本该分开的操作被合并进同一个序列了。

当你看到这些迹象时，问题通常不是“太 imperative”，而是“imperative 放错了地方”——该被提取出来变成可测试东西的 decision logic，没有被提出来。修复它通常不是让代码整体更不 imperative，而是把 _决定_ 的部分与 _行动_ 的部分分开。

考虑下面这个把两者交织在一起的 function：

```python
def process(order_id: int) -> None:
    row = db.fetch_order(order_id)          # I/O
    if row.status == "paid" and row.total > 100:   # decision
        discount = row.total * 0.1          # decision
        db.apply_discount(order_id, discount)   # I/O
        mailer.send(row.email, "discount applied")  # I/O
```

这个规则（paid 且超过 100 的订单打 9 折）不能在不依赖 database 和 mailer 的情况下测试。把 decision 提出来，它就变成了一个你可以用普通值测试的纯函数，而 imperative shell 只保留 I/O：

```python
def compute_discount(order: Order) -> Decimal:   # pure, trivially testable
    if order.status == "paid" and order.total > 100:
        return order.total * Decimal("0.1")
    return Decimal(0)

def process(order_id: int) -> None:              # thin imperative shell
    order = db.fetch_order(order_id)
    discount = compute_discount(order)
    if discount:
        db.apply_discount(order_id, discount)
        mailer.send(order.email, "discount applied")
```

## Procedural decomposition

Procedural style 不只是“一长串函数”。它的纪律在于把流程拆成若干命名的 procedures，每个 procedure 都处于同一抽象层级。一段好的 procedure 会像一系列调用一样可读，而这些调用的名字本身就能讲故事；你不需要深入任何一个就能理解流程。当你发现自己需要加注释来标记某个块（`# now validate the records`）时，这个块通常更适合变成一个命名函数（`validate_records(...)`）。注释会腐坏，而函数名每次都会被读者重新检查。

让每个 procedure 保持在同一抽象层级。把高层 orchestration（`run_job`）和底层字节操作放在同一个 function 里，会迫使读者不停切换视角。把细节下沉到自己的 procedures 里，让调用者保持为一段可读的摘要。

## 与 functional core / imperative shell 的关系

最清晰的解决方式，是保留 imperative style，但把它限制在一个薄薄的外层。这就是 [functional-core.md](./functional-core.md) 里的 imperative shell：shell 负责安排 I/O、transactions、retries 和 logging；core 接收普通 data，应用规则，并返回普通 data。Shell 故意保持 imperative——因为有序副作用就住在那一层。你需要移出去的是 decision-making，而不是 orchestration。

这也与 [data-oriented.md](./data-oriented.md)（shell 传给 core 的 data）以及 [resource-lifecycle.md](./resource-lifecycle.md)（shell 如何获取并释放它所安排的资源）相关联。

## 在 Python 中

- 把 imperative wiring 放在明确的 entry point 中，例如 `main(argv: Sequence[str] | None = None) -> int`，并通过 `if __name__ == "__main__":` 将其隔离。
- 让 entry layer 负责解析参数、加载 config、配置 logging、构建 dependencies，并把异常转换成 exit code。Core logic 接收显式参数，并保持可导入、可测试。
- 对外部资源使用 `with` / `async with`，不要依赖 garbage collection 来释放它们——见 [resource-lifecycle.md](./resource-lifecycle.md)。
- 当一个 procedure 超出可读性时，按阶段拆成命名步骤（`load_config()`、`build_client()`、`run_job()`），再考虑 framework。线性且命名良好的步骤本身就是一种特性，而不是 smell。
- 抵制把一个简单的三行序列包进 class 或 pipeline abstraction 的冲动；直接的 imperative code 往往就是符合 KISS 的答案。
