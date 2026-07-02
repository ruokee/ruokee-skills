# pre-commit

pre-commit 是一个 Git hook framework 和多语言 hook environment manager。它会把 hook 安装到本地仓库中，使快速且确定性的检查在提交落地前运行，在格式、基本文件卫生和明显 lint 失败到达 review 之前就把它们拦住。hook 先在本地运行；是否集成 CI 取决于项目本身。

## Hook 框架

配置写在 `.pre-commit-config.yaml` 中，而不是写在 `pyproject.toml` 中。这是一个工具事实：pre-commit 读取的是自己的配置文件，想为了配置集中化而把 hook 定义塞进 `pyproject.toml` 是做不到的。每个 hook 都声明一个 repo、一个 revision，以及要运行的 hook ID。pre-commit 会为每个 hook repo 创建并缓存一个隔离环境，因此 hooks 不依赖项目虚拟环境里碰巧安装了什么。

```yaml
repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.6.0
      hooks:
          - id: ruff-format
          - id: ruff
            args: [--fix]
    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v4.6.0
      hooks:
          - id: trailing-whitespace
          - id: end-of-file-fixer
          - id: check-yaml
```

## 本地提交门禁

在执行 `pre-commit install` 之后，hooks 会在 `git commit` 时自动对已暂存文件运行。其目的就是在提交时而不是在 review 时，拦住那些琐碎问题 - 格式漂移、残留空白、坏掉的 YAML。保持 hook 集合小而快，让门禁低摩擦；如果门禁太慢，人们就会养成使用 `--no-verify` 直接跳过它的习惯。

## 常见 hooks

典型的 Python 组合包括：文件卫生 hooks（`trailing-whitespace`、`end-of-file-fixer`、`check-yaml`、`check-added-large-files`）、用于格式化和 lint 的 [`ruff-format`](ruff.md) 和 `ruff`，以及用于项目专属规则的自定义 [Flake8 plugin](flake8-plugin.md)。可以加入类型检查 hook，但整个仓库的类型检查通常对每次提交来说太慢，更适合放在 CI 中，而 editor LSP 则提供快速的本地反馈。

## 自动修复 hooks 与文件修改

有些 hooks 会修改文件：`ruff-format`、`ruff --fix`、`end-of-file-fixer` 和 `trailing-whitespace` 都会原地重写内容。当 hook 改动了文件时，pre-commit 会报告失败并把修复留在未暂存状态，这样你可以先审查改动，再重新暂存后提交。这是有意设计的 - 你会看到到底被重写了什么，而不是盲目提交机器编辑。

## 速度考虑

第一次运行会安装 hook 环境，因此会比较慢；这是正常现象，不应因此把 pre-commit 当成 CI 的替代品。后续运行会重用缓存环境。把提交 hook 留给快速、确定性的检查，把完整测试、coverage 和依赖网络的扫描放到 CI 或手工任务里。

## 可选的 CI 集成

pre-commit 只能捕捉那些安装了 hooks、且没有跳过它们的贡献者的问题，因此 CI 必须重复关键检查。常见做法有两种：托管的 pre-commit.ci 服务，它会在 pull request 上运行相同配置并可自动修复；或者在 CI 步骤里手动运行 `pre-commit run --all-files`。并不是每个项目都有 CI，所以应把这一层视作可选而不是默认假设；但只要存在，它就应当镜像本地 hook 配置，使本地和 CI 结果一致。
