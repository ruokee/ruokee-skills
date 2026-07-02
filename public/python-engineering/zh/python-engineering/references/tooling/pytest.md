# pytest

pytest 是非一次性项目的默认 test runner。它处理测试发现、fixtures、parametrization、markers、断言内省以及运行入口。它不会直接规定生产代码风格，但它注入依赖和隔离行为的方式，会推动代码变得可测试。

## 测试发现

默认情况下，pytest 会收集匹配 `test_*.py` 或 `*_test.py` 的文件、前缀为 `test_` 的函数，以及前缀为 `Test` 且没有 `__init__` 的 class。应配置 `testpaths`，让收集从正确位置开始：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

把测试放在顶层 `tests/` 目录中，可以让它们不进入 shipped package，同时让发现行为更可预测。

## `conftest.py`

`conftest.py` 用于存放在目录子树中共享的 fixtures、hooks 和 plugin 配置，而不需要显式 import。pytest 会自动加载它。根部的 `conftest.py` 让 fixtures 全局共享；嵌套的 `conftest.py` 则将 helper 限定在子树内。它适合放共享 fixture 和 hook 实现，而不是用来堆放那些用普通 import module 反而更清楚的测试 helper。

## Fixture 作用域

fixture 有一个 `scope`：`function`（默认）、`class`、`module`、`package` 或 `session`。更宽的作用域可以跨更多测试共享昂贵的 setup（数据库、server），但会以隔离性换速度。作用域应与资源的成本和可变性相匹配：临时目录每个 function 一个，唯读 fixture 每个 session 一个。`yield` fixture 会在 `yield` 之后执行 teardown，这就是释放资源的惯用方式。

```python
import pytest

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine()
    yield engine
    engine.dispose()
```

## Parametrize

`@pytest.mark.parametrize` 会让一个测试函数在多个输入上运行，每个输入都是一个独立报告的 case。它替代手写循环，让失败明确指出具体输入。可使用 `ids` 让 case 名更易读，也可以叠加多个 parametrize 装饰器来取输入集的笛卡尔积。

```python
@pytest.mark.parametrize("value,expected", [(2, 4), (3, 9)])
def test_square(value, expected):
    assert square(value) == expected
```

## Markers

marker 用来给测试打标签以便选择：内建的有 `skip`、`skipif`、`xfail`，也可以定义自定义 marker，如 `slow` 或 `integration`，并用 `-m` 选择。自定义 marker 应在配置中注册，这样拼写错误不会悄悄创建一个新 marker。`--strict-markers` 会把未注册 marker 变成错误，值得开启。

```toml
[tool.pytest.ini_options]
markers = ["slow: long-running tests", "integration: needs external services"]
```

## Import 模式

import mode 决定测试 module 如何进入 `sys.path`。旧的 `prepend` 模式会插入 rootdir，并依赖 `__init__.py` 的摆放，这可能掩盖 packaging 错误。新项目应优先使用 `--import-mode=importlib`，它在不修改 `sys.path` 的情况下 import 测试 module，从而避免名字冲突和意外的 import 副作用。

```toml
[tool.pytest.ini_options]
addopts = "--import-mode=importlib"
```

## Strict 模式

`--strict-markers` 和 `--strict-config` 会把未知 marker 和配置问题变成硬失败，从而尽早暴露错误。它们值得开启，但也会把测试套件与 pytest 当前行为绑定在一起，因此应 pin pytest 版本。如果你不想自动吸收未来的严格性变化，那就启用具体的 strict 选项，而不是依赖一个宽泛模式。

## 插件生态

pytest 拥有庞大的 plugin 生态：`pytest-cov` 用于 coverage，`pytest-xdist` 用于并行运行，`pytest-asyncio` 用于 coroutine 测试，以及许多 framework 集成。添加 plugin 应基于真实需求，而不是默认全开；每个 plugin 都是一个 dependency 和一个潜在的收集或 fixture 意外来源。coverage 本身尤其可以直接通过 [coverage.py](coverage.md) 运行，而无需插件。

pytest 能验证代码是否运行，并对行为做断言，但一个通过的测试套件并不能证明断言有意义，也不能证明边界情况已覆盖。coverage 工具回答的是执行了什么；只有断言才回答它是否正确。
