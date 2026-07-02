# coverage.py

coverage.py 衡量测试运行期间哪些代码行和分支被执行。它不是测试框架，也不是单独的质量指标；它是测试执行之上的一层可观测性，回答的是“测试实际触达了什么”，而不是“测试有没有检查对”。

## Statement coverage 与 Branch coverage

Statement coverage 记录哪些行执行过。Branch coverage 还会记录每个条件的哪些分支被走过，因此一个 `if` 的 `else` 路径从未被触达时，即使每一行都跑过，也会显示为 partial branch。Branch coverage 能捕获 statement coverage 看不到的未测试决策路径，核心逻辑和 library 很值得启用它。

```toml
[tool.coverage.run]
branch = true
source = ["mypackage"]
```

## 运行 coverage

原生命令很直接，也避免额外 plugin 依赖：

```bash
coverage run -m pytest
coverage report -m
coverage html
```

`coverage run` 记录执行，`report` 打印终端摘要（`-m` 会显示缺失行号），`html` 则生成可浏览的标注报告。`pytest-cov` 可以把 coverage 集成进 pytest 调用，使用上很方便，但它只是可选项，并非必需。

## 配置

在 `pyproject.toml` 中用 `[tool.coverage.*]` 进行配置。`source` 用于把测量范围限制在你的 package，这样第三方代码不会稀释数字。`omit` 用来排除生成代码或 migrations 等文件。`[tool.coverage.report]` 控制 `exclude_lines`（例如 `pragma: no cover`、`if TYPE_CHECKING:` 和 `raise NotImplementedError`）以及 `fail_under` 阈值。

```toml
[tool.coverage.report]
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:"]
fail_under = 80
```

## 阈值策略

`fail_under` 会在总覆盖率低于某个百分比时使运行失败。应从一个现实且当前可达到的数值开始，然后逐步提高；阈值若远高于现实，只会训练人们去绕过它。高百分比也不等于高质量，因为 coverage 只统计执行，不统计断言强度。

## coverage 衡量什么，不衡量什么

coverage 只能告诉你一行或一个分支在测试套件中是否被执行过。它不能说明是否对结果做了断言、是否测试了边界值，或者错误路径是否被有意义地验证过。代码可以在 100% coverage 下依然只有“什么都没 assert”的测试。应把 coverage 当作一个用来暴露明显未测试代码的底线，而不是行为正确性的证据。

## CI 门禁

coverage 通常在 CI 中运行，由阈值门禁统一对所有贡献者生效。在本地，它按需运行，而不是每次提交都运行，因为完整的 coverage 运行比适合 commit hook 的快速检查要慢。CI 中应将 [coverage.py](coverage.md) 与 [pytest](pytest.md) 结合运行，并把阈值作为本地和 CI 调用共同引用的唯一事实来源。
