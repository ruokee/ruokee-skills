# Project Structure

一个长期维护的 Python 项目，不应该只是“当前工作目录碰巧能 import 的一个目录”。结构存在的意义，是让 importable package、tests、工具配置、运行入口、依赖声明和部署边界都各有明确归属。什么形态合适，取决于项目的使用方式和预期寿命；本文覆盖每种常见形态，以及让项目从一种形态迁移到下一种形态的信号。

## 单文件脚本

一个单独的 `.py` 文件适合一次性自动化、小工具和实验。借助 PEP 723 的内联脚本 metadata，即使是独立文件也可以在注释块中声明依赖和所需 Python 版本，因此像 `uv run script.py` 这样的 runner 可以在没有外围 project 的情况下构建隔离环境：

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
import httpx
```

这适用于脚本确实很小、没有测试需求、也不是长期维护组件的时候。它已经超出单文件的增长信号包括：开始积累多个 helper function、需要自己的测试、长出一个配置文件，或者别的代码想要 import 它的一部分。到了那一步，应当把它提升为真正的 package，而不是让它变成永久追加的大杂烩脚本。

## Flat layout

flat（或“no-src”）layout 会把 import package 直接放在 project root 下：

```text
project/
├── pyproject.toml
├── mypkg/
│   ├── __init__.py
│   └── app.py
└── tests/
    └── test_app.py
```

它直观、启动成本低，在小型 library、历史项目和简单内部工具中很常见。它的结构弱点在于，project root 会自然进入 `sys.path`，因此本地测试和脚本倾向于 import _source directory_ 而不是 _installed artifact_ - 这会掩盖 packaging 错误，例如 built wheel 中缺少某个文件。

真正的退化风险并不在 flat layout 本身，而在它退化成“一个大型脚本目录”：`run.py`、`utils.py`、`db.py`、`api.py` 散落在根目录，彼此通过当前目录互相 import，入口逻辑和 library 逻辑缠在一起，import 时的副作用没人能追踪。如果选择 flat layout，仍然应保持清晰的 package 目录，将 entry scripts 与可 import 的逻辑分开，并禁止沉重的 import-time side effects（读取环境、打开连接、启动线程）。

## Src layout

src layout 将预期的 import package 移入 `src/` 子目录：

```text
project/
├── pyproject.toml
├── README.md
├── src/
│   └── mypkg/
│       ├── __init__.py
│       └── app.py
└── tests/
    └── test_app.py
```

这种分离的目的在于 _import safety_：由于 `src/` 默认不在 `sys.path` 上，因此你不会不小心从源码树里 import 到 package。测试运行的是 _已安装_ 的 package（通过 editable install），因此它们会执行真实用户将看到的相同 import path 和 packaging 边界。这能捕获一类 flat layout 会掩盖到发布阶段才暴露的 bug - 例如某个 module 没被打包、某个 data file 没被包含。

对于任何会发布、部署或长期维护的项目，都应选择 src layout：library、SDK、framework、CLI、web service，以及 workspace 成员。代价是初始心智模型稍微复杂一些（即使是 editable，也必须 install package 才能运行），换来的是测试所见即所得。本地开发应使用 editable install 或等价的 uv 管理环境；不要依赖手工编辑 `PYTHONPATH`。

## Packaged application

packaged application 是可安装、可运行、可部署的 - CLI、web/API service、background worker，或内部平台工具 - 由 `[project]` metadata 描述，而不是作为零散脚本散放：

```text
project/
├── pyproject.toml
├── uv.lock
├── README.md
├── src/
│   └── app_name/
│       ├── __init__.py
│       ├── __main__.py
│       └── cli.py
└── tests/
    └── test_cli.py
```

`[project]` 表声明 `name`、`version`（或 `dynamic`）、`requires-python` 和 `dependencies`。入口点应放在 `[project.scripts]` 中，这样工具是通过名字调用，而不是通过 `python src/app_name/main.py`。非运行时 dependencies - dev、test、lint、docs - 应放在 dependency groups 中，排除在 runtime 集合之外（见 [dependency-management](dependency-management.md)）。lockfile 则固定部署环境。

常见误解是“installable”就意味着“必须公开发布”。并不是。私有 application 会被构建成 wheel 用于内部部署；要防止它被意外发布，关键在于：CI 中不要有公开 PyPI token，默认不要有发布步骤，名字也不要冒充公共 package。

## Workspace

workspace 是一个多 package 仓库，其中若干 package 或 application 共享一个 lockfile 和一组工具入口。uv workspace 适用于一个 application 加共享 library、一组 service，或一个共同演进的内部 package monorepo：

```text
repo/
├── pyproject.toml
├── uv.lock
├── packages/
│   ├── app-api/
│   │   ├── pyproject.toml
│   │   └── src/app_api/
│   └── shared-domain/
│       ├── pyproject.toml
│       └── src/shared_domain/
└── tests/
```

只有在确实至少有两个职责可明确描述的 package、它们之间有清晰的依赖 _方向_，并且共享 package 暴露的是稳定 API 而不是从 application 中临时切出来的内部目录时，才应引入 workspace。workspace root 负责共享工具配置和整个仓库的命令；每个成员负责自己的 metadata 和运行时 dependencies。application 成员不能触碰共享 package 的 internals - 它们只应依赖其 public API 和声明的方向。

不要仅仅因为目录很多、或者想按文件夹拆开一个大型 application、或者 packages 彼此 import 对方 internals 但没有稳定边界，就去使用 workspace。若没有整个仓库级别的测试、类型检查和依赖升级策略，workspace 只会放大耦合，而不是收束耦合。

## 决策表

|项目类型|推荐布局|迁移升级信号|
|-|-|-|
|一次性自动化、实验|单文件脚本（PEP 723）|多个 helper、需要测试、配置文件，或另一个 module 想 import 它|
|小型 library、简单内部工具|Flat layout|出现多个入口点、dependency groups，或 packaging 错误开始漏出|
|已发布 library、SDK、framework|Src layout|（任何长期维护或发布的项目都默认如此）|
|CLI、web/API、service、内部应用|Packaged application（src + `[project]`）|需要部署产物、入口点和 lockfile|
|应用 + 共享 library、service 组、monorepo|Workspace|两个以上 package、有稳定 API 和清晰依赖方向|

如果在 flat 和 src 之间犹豫，而这个项目会持续超过一周，那么优先选 src：import safety 的保证是防止 packaging 意外的廉价保险。

## 测试目录、配置与入口点

在所有 packaged 形式中，tests 都应放在顶层 `tests/` 目录，而不是放进生产 package 内，除非所在生态有强烈相反约定。测试文件和函数应按 _行为_ 而不是机械地按实现文件命名；对于大型 framework 和 SDK， loosely mirroring package tree 有助于定位测试。测试 runner 应显式指向测试目录（`testpaths = ["tests"]`），这样它不会误入临时目录或已构建文档。coverage 的 source 应该指向实际 package path，这样工具和脚本就不会污染生产覆盖率数字。更详细的测试约定见 [testing](../spec/testing.md)。

工具配置集中在 `pyproject.toml` 的 `[tool.*]` 下，真正需要独立文件的工具除外（pre-commit 仍使用 `.pre-commit-config.yaml`）。已安装命令的入口点应放在 `[project.scripts]` 中；`__main__.py` 用于支持 `python -m app_name`。指导原则是：project shape、dependency groups、test scope 和 type-check scope 都应当在配置中 _显式_ 表达，而不是依赖当前目录碰巧能 import 什么。
