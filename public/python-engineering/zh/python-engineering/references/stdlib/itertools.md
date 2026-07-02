# itertools

`itertools` 提供一组 iterator building blocks，可以组合成 lazy data pipeline。每个函数都消费并产生 iterator，一次只计算一个值，而不是先物化中间列表。这样可以在大规模或无限序列上保持内存平稳，也让 pipeline 能够提前停止而不做多余工作。

## 惰性求值

itertools pipeline 在没有东西拉取之前不会做任何工作。把 `map`、`filter` 和 itertools 函数组合起来描述的是一次计算；真正迭代时，才会按元素逐个执行。它的收益是节省内存和短路：向 `next()`、`any()` 或切片式 consumer 提供的阶段，不会处理超过 consumer 要求的元素。

```python
from itertools import islice

# Reads only the lines needed, not the whole file.
first_errors = islice((ln for ln in log_file if "ERROR" in ln), 10)
```

代价是惰性很容易丢失。在阶段外层包上 `list()`、`sorted()` 或 `len()` 会强制完整求值；只有在你真正需要 concrete collection 的地方才这样做。

## 常见用法

- `chain(a, b, ...)` 和 `chain.from_iterable(iterables)` 可以在不构建合并列表的情况下连接 iterable - 适合扁平化一层。
- `islice(it, start, stop, step)` 用于切片 iterator。与列表切片不同，它不能向后索引，但可以作用于无限和流式源。
- `groupby(it, key)` 会把 _连续_ 且 key 相同的元素分组。输入必须事先按该 key 排序，否则 group 会碎裂。这常让以为它像 SQL grouping 的新手踩坑。
- `product`、`permutations`、`combinations` 可以惰性地产生组合序列 - 对测试矩阵和参数扫描很有用，但增长是指数级的，因此要限制输入规模。
- `pairwise(it)`（3.10+）产生重叠的相邻对 `(s0,s1), (s1,s2), ...`，比手工按索引 zip 更适合做差分和窗口。
- `starmap(func, arg_tuples)` 将预先分组好的参数 tuple 应用于函数 - 当参数已经打包好时，它就是 `map`。
- `batched(it, n)`（3.12+）会产生最多 `n` 个元素组成的 tuple，是分页请求或批量写入时对流进行分块的标准方式。3.12 之前则可用基于 `islice` 的 helper 实现同样角色。
- `accumulate`、`takewhile`、`dropwhile`、`count`、`cycle`、`repeat`、`tee`、`zip_longest`、`compress`、`filterfalse` 覆盖了 running totals、条件切片和流对齐。

## 何时有帮助，何时会遮蔽

当 itertools 能命名一个公认操作时，它会提升清晰度：`batched` 说的是“分块”，`pairwise` 说的是“相邻窗口”，`chain` 说的是“连接”。熟悉这些术语的读者会比看手写索引算术更快理解意图。它在数据无法装入内存或源本身无限时也尤其重要 - 这种情况下，lazy pipeline 是唯一合理的形态。

当普通 comprehension 或 loop 更直接时，它就会遮蔽含义。`chain` / `filter` / `starmap` / `takewhile` 的深层堆叠可能会把真实变换藏在 composition 之后；一个 body 清晰的单个 `for` loop 往往更好。只有在它确实减少了 bookkeeping 时才使用 itertools，而不是为了在简单逻辑上再加一层间接。

## 多次消费陷阱

iterator 在遍历一次后就会耗尽。这是最常见的 itertools bug：

```python
results = map(transform, records)   # an iterator, not a list
total = sum(r.size for r in results)
for r in results:                   # empty — already consumed by sum()
    save(r)
```

如果必须遍历数据两次，就要先物化一次（`results = list(map(...))`），或者使用 `itertools.tee` 复制 iterator。注意，`tee` 会缓存从一条分支消费、但另一条分支尚未消费的内容，因此两条分支如果推进速度相差很大，内存消耗可能和 list 一样 - `tee` 只在分支大致同步前进时才有帮助。同样的单次遍历规则也适用于 `groupby`：它的 group iterator 只有在你前进到下一个 group 之前才有效，因此如果之后还要用，就应先把 group 内容捕获下来。
