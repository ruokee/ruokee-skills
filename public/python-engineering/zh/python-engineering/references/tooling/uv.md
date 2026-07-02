# uv

uv 是一个 Python project 和 environment manager：它解析依赖、构建 lockfile、运行脚本、管理工具安装，并提供 Python 解释器。它回答的是“这个项目使用哪个 Python、安装了哪些 dependency、环境如何复现、工具如何运行”，而不是规定代码风格。

uv 把过去需要 pip、pip-tools、pipx、virtualenv 和版本管理器分别完成的工作统一起来。它速度很快，而且默认就会写 lockfile，这让可复现环境成了最省力的路径。

## 项目创建

`uv init` 会 scaffold 一个项目，包含 `pyproject.toml`、一个固定本地解释器的 `.python-version` 文件，以及一个起始的 source layout。`[project]` 表负责 `requires-python`、依赖列表和 packaging metadata。`requires-python` 应有意识地设定，因为它会影响版本条件语法决策，并约束 resolver。

```bash
uv init my-project
cd my-project
uv add httpx
```

## 依赖管理

`uv add <pkg>` 和 `uv remove <pkg>` 会同时编辑 `pyproject.toml` 并更新 lockfile。`uv lock` 只重新解析而不安装，`uv sync` 则让环境与 lockfile 完全一致，移除未声明的内容。环境被视为派生状态：在 `pyproject.toml` 中声明意图，让 lockfile 和 `.venv` 去跟随它。

```bash
uv add "fastapi>=0.115"
uv add --dev pytest ruff
uv remove requests
```

## lockfile

`uv.lock` 会跨平台记录完整解析后的 dependency graph 和 hash。对于 application，应提交它，这样每台机器和每次 CI 运行都安装相同版本。只有那些必须针对一组依赖版本重新解析的 library，才是通常不提交 lockfile 的主要场景，但大多数 repository 都会从检查入库的 lockfile 中受益。

## 依赖组

开发、测试、lint 和 typing 依赖应放在 groups 中，而不是 runtime dependency 列表中，这样它们可以被选择性安装，并且不会进入发布产物。默认 dev group 用 `uv add --dev`，命名 group 则用 `--group <name>`。具体表结构取决于当前 uv 版本对 `[dependency-groups]` 和 `[tool.uv]` 的支持方式。

## 脚本执行

`uv run <command>` 会在受管理环境中执行，必要时先同步，因此贡献者不需要手动激活 virtualenv，也不会拿到过时环境。所有工具调用都应通过它路由，以保持本地和 CI 行为一致。

```bash
uv run pytest
uv run ruff check
uv run python -m myapp
```

单文件脚本使用 PEP 723 内联 metadata：在文件顶部用注释块声明依赖，`uv run script.py` 就可以在没有项目的情况下 provision 一个临时环境。

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
import httpx
```

## 工具管理

`uv tool install` 和 `uv tool run`（别名 `uvx`）用于在隔离环境中管理独立 CLI 工具，承担 pipx 所做的角色。这适合那些全局有用、但不是项目依赖的工具。项目级质量工具则更适合声明为 dependency-group 成员并通过 `uv run` 执行，这样它们的版本会和检查的代码一起被锁定。

```bash
uvx ruff check
uv tool install pre-commit
```

## Workspace

workspace 把多个相关 package 组织在一个 lockfile 和共享解析之下，类似 Cargo 或 npm workspaces。成员通过 `[tool.uv.workspace]` 声明。适用于一个应共享单一解析的共同开发 package monorepo；如果只是几个碰巧放在同一目录下的无关项目，就不要使用，因为共享解析会把它们的依赖约束绑在一起。

## Python 版本管理

uv 会下载并管理独立的 CPython 构建，因此只要有 `requires-python` 和 `.python-version`，就能获得匹配的解释器，而不需要 pyenv 之类的独立工具。`uv python install 3.12` 可以 provision 某个版本，而 resolver 在选择解释器时会遵循项目声明的边界。

## 与 pip、pipx 和 Poetry 的关系

uv 覆盖了 pip（安装）、pip-tools（lock）、pipx（工具隔离）、virtualenv（环境）以及版本管理器分别完成的工作。与 Poetry 相比，它们在项目和依赖管理上有重叠，但 uv 更强调速度和更广泛的环境角色。工具之所以值得采用，是因为它又快又统一；它并不能替代类型检查、测试、coverage 或 CI，后者仍然负责把关正确性。现有的 Poetry 或 Hatch 项目、带有自身约束的已发布 library，以及组织标准化设置，都应根据自身价值迁移，而不是自动迁移。
