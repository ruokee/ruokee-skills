# Python Version Policy

一个项目并不是运行在抽象的“Python”上，而是运行在一组版本范围上，而这个范围是一项会影响语法、依赖和部署的设计决策。这里有两个数字，而且它们并不相同：代码必须支持的 _最低_ 版本，以及开发和 CI 所假定的 _目标_ 版本。

## 最低版本与目标版本

最低版本是 floor - 代码保证可以 import 和运行的最老解释器。它由 `requires-python` 声明，并约束所有地方可用的语法和标准库 API。如果 floor 是 3.10，那么 shipped code 中任何地方都不能使用 `type X = ...` alias 或 PEP 695 generic parameters，因为 3.10 解释器会在任何逻辑运行前就抛出 `SyntaxError`。

目标版本是你开发时针对的版本、在本地锁定的版本（通常通过 `.python-version`），以及 CI 中首先运行的版本。它通常是依赖链支持的最新版本。代码仍必须保持在 minimum 的语法范围内，但 target 是你能获得最快解释器、最好错误信息，以及未来弃用的早期预警的地方。

一个健康的项目会有意识地让二者保持一致：CI matrix 同时运行 floor 和 target（有时还会运行中间几个点），这样一旦某个特性不小心要求了更高版本，就会尽早失败，而不是到了用户安装时才暴露。

## 如何确定最低版本

floor 不是偏好，而是若干硬约束中的最大值。确定它时，要问真正必须运行代码的是什么：

- **运行环境。** 如果代码部署在受管平台、基础镜像或固定解释器版本的 OS package 上，那么那个版本就是硬下界。若唯一可用运行时只提供 3.11，你就不能要求 3.12。
- **依赖兼容性。** 每个 dependency 都声明自己的 `requires-python`。项目的 floor 不能低于其依赖中最高的 floor。只要有一个 library 需要 3.11，整个项目就被拉到 3.11。
- **部署平台。** Serverless 运行时、Linux 发行版和公司基础镜像通常都会落后于最新发布版本。floor 必须是这些目标实际提供的版本。
- **CI matrix 范围。** 你愿意并且能够测试的版本构成了实际支持集。声称支持一个从未在 CI 中运行的版本，本质上是没有验证的承诺。

floor 应当取这些下界中的最高者。再低，某处就会坏掉；再高，用户或环境会被无谓地排除。

## 版本受限特性

每个较新的发布都会带来一些能力，而这些能力只有在 floor 升到相应版本后才能使用。选择 floor 也就等于选择以下能力是否可用：

- **3.10** 带来 structural pattern matching（`match`/`case`）、注解中的 `X | Y` union operator，以及带括号的 context managers。关于 pattern matching 何时值得采用，见 [match-case](../grammar/match-case.md)。
- **3.11** 带来用于并发和批处理失败的 `ExceptionGroup` 和 `except*`、通过 `add_note()` 添加 exception notes，以及 typing 中的 `Self`。见 [exception-groups](../grammar/exception-groups.md)。
- **3.12** 带来 PEP 695：`type X = ...` alias 语句以及内联 generic parameters（`def f[T](x: T) -> T`），还有 `typing.override`。这些特性去掉了大部分 `TypeVar` / `Generic` 样板，但也是严格的语法门槛 - 见 [type-hint](../spec/type-hint.md)。
- **3.13** 带来 `warnings.deprecated()` 这一同时面向 runtime 和 static 的弃用标记、type parameter defaults，以及实验性的 free-threaded 构建。
- **3.14** 默认启用 deferred annotation evaluation（PEP 649/749）、提供用于读取 annotations 的 `annotationlib`，以及 template strings。任何在 runtime 读取 annotations 的代码 - framework、ORM、serializer、DI container - 都需要针对这一行为做验证；见 [type-hint](../spec/type-hint.md)。

特性可用并不意味着就应该使用。Pattern matching、exception groups 和 generics 各自都有很窄的适用区间；这个门槛只决定选项是否存在。

## `requires-python` 语义

`[project]` 中的 `requires-python` 是对 _安装者_ 解释器的约束，而不是构建时固定的版本。像 `">=3.12"` 这样的 specifier 告诉 installer 和 resolver：这个 package 不接受更老的版本，同时也让 dependency resolver 可以为“你的 package”选择与“他们的环境”兼容的版本。它不会下载或切换解释器；它只是声明契约。

要让 `requires-python`、本地 `.python-version` 和 CI matrix 保持一致。当它们漂移时 - 例如 `requires-python = ">=3.10"`，但所有开发者都在跑 3.12，而 CI 从不测试 3.10 - floor 就会变成空话，3.10 不兼容的语法也可能悄悄混入而不被发现。

## Docker 与基础镜像

当部署产物是容器时，基础镜像 tag 本身就是版本策略的一部分。要锁定具体的 minor version（例如 `python:3.12-slim`），而不是浮动的 `python:3` 或 `python:latest`，这样运行时就不会在构建之间自行漂移。镜像中的解释器应当与 target version 一致，并且必须满足声明的 floor。slim 和 distroless 变体可以减少 surface area，但也会改变系统库的可用性，这对带有编译扩展的 package 可能很重要。

## 何时提高最低版本

提高 floor 对使用旧解释器的人来说是 breaking change，因此它必须有比“新鲜感”更充分的理由。好的理由包括：

- 你需要的某个 dependency 本身已经放弃了对旧版本的支持，迫使你跟着上调。
- 旧版本已经到达 end-of-life，不再收到安全修复。
- 某个版本受限特性能够显著简化代码，而且旧版本的用户群已经消失或几乎可以忽略。
- 部署和 CI 目标都已经迁移，旧 floor 在实践中也早已无人测试。

当你确实要提高 floor 时，应当把它作为一个有意且公开的变更来做：一次性更新 `requires-python`、CI matrix、基础镜像，以及所有兼容性 shim，然后再开始使用新的语法。提高 floor 和引入 3.12-only 语法应该是同一个决定，而不是两个偶然。
