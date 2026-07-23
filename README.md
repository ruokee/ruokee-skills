# ruokee-skills

Ruokee 的个人 Agent Skills 与本地插件工作仓库。

仓库统一使用 `plugins/<name>/` 表达 11 个插件工作区。每个工作区包含 schema 2 `meta.toml`，实际 package root 中保留 Codex 与 Claude Code 的原生 manifest；Pi 从同一个 package root 的 `skills/` 约定目录发现 Skill。`task` 是例外：它的工作区位于 `plugins/task/`，三个宿主实际安装 `plugins/task/package/`。

```text
plugins/<name>/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── skills/<name>/SKILL.md
├── variants/<variant>/       # 仅非 default overlay
├── meta.toml
└── README.md
```

default 变体都是完整的英文 base。`variants/zh/` 只保存相对 base 有差异的文件，物化时先复制 base，再覆盖 overlay。`classification` 与 `experimental` 只描述仓库属性，不影响 marketplace 可见性。

## Codex

先把当前 checkout 注册为本地 marketplace，再用宿主原生命令安装 default：

```bash
codex plugin marketplace add /path/to/ruokee-skills
codex plugin list --marketplace ruokee-skills
codex plugin add code-quality@ruokee-skills
```

Codex marketplace 当前是用户级入口。插件 Skill 使用 `plugin-name:skill-name` 命名空间；项目 local Skill 使用裸名，两者可以同时出现。

## Claude Code

```bash
claude plugin marketplace add /path/to/ruokee-skills --scope user
claude plugin install code-quality@ruokee-skills --scope user
claude plugin list
```

仓库脚本不使用 Claude Code 的 project/local plugin scope 来实现项目变体，因为同一用户下的已安装内容仍来自共享 cache。项目隔离由 standalone Skill 完成。

## Pi

Pi 第一阶段只支持 checkout 后的本地路径 Package：

```bash
pi install /path/to/ruokee-skills/plugins/code-quality
pi install /path/to/ruokee-skills/plugins/task/package
```

除 Task 外的 10 个插件直接使用约定目录，不额外添加 `package.json`。Task 的 `package.json` 显式登记 Skill 与 extension。Pi 的 Git source 不能选择 monorepo 子目录，本仓库暂不承诺远程单插件安装。

## 非 default 变体

用户级 default 优先使用上面的宿主原生命令。选择非 default 变体时，安装器先验证或完成原生安装，再在同一个插件/Package 入口应用 overlay：

```bash
uv run scripts/install.py setup code-quality --scope user --variant zh
uv run scripts/install.py update code-quality --scope user
uv run scripts/install.py reset code-quality --scope user
```

默认处理 Codex、Claude Code 和 Pi，任一宿主 CLI 缺失都会在写入前失败。用可重复的 `--host` 缩小范围：

```bash
uv run scripts/install.py setup code-quality --scope user --variant zh --host codex --host claude
```

用户状态写入 `$XDG_STATE_HOME/ruokee-skills/installs.json`。Codex/Claude 变体写入经宿主状态验证的 plugin cache；Pi 非 default 变体使用 `$XDG_DATA_HOME/ruokee-skills/packages/<plugin>` 受管副本，不修改仓库 checkout。

直接执行宿主原生 update 可能暂时把 Skill 恢复为 default；再次运行仓库 `update` 才会解析新安装位置并重放已记录变体。`reset` 只恢复 default 并清理变体状态，不卸载用户 plugin/Package；真正卸载继续使用宿主原生命令。

## 项目 local Skill

项目 scope 必须显式提供消费项目，且不会修改用户 cache 或 `.pi/settings.json`：

```bash
uv run scripts/install.py setup code-quality --scope project --project /path/to/project --variant zh
uv run scripts/install.py update --scope project --project /path/to/project
uv run scripts/install.py reset code-quality --scope project --project /path/to/project
```

Codex 与 Pi 共用 `<project>/.agents/skills/<name>`，Claude Code 使用 `<project>/.claude/skills/<name>`。两个项目可以选择不同变体。安装器默认拒绝同名非托管目录和已漂移的托管内容；`setup --force` 可以替换它明确报告的项目目标，`update/reset --force` 只接受带有效本仓库所有权元数据的目录。

Task 的项目 local 只物化 Skill，MCP 与 Pi extension 仍来自用户级 package。未安装所选宿主的 Task runtime 时，安装器会在写入项目前拒绝。

## 元数据与上游维护

每个 `plugins/<name>/meta.toml` 只有一套分类、实验状态、package root、default base 和可选 `[upstream]` 语义。`third-party` 与 `fork` 插件的 `[upstream].managed_paths` 相对 default Skill 根解析；仓库独有文件不得列入。

```bash
scripts/check-skill-updates.py check --json
scripts/check-skill-updates.py diff <skill-name>
scripts/check-skill-updates.py update <skill-name> [<skill-name> ...]
```

检查以 `managed_paths` 的内容差异为准。上游 ref 已推进但托管文件未变化时报告 `ref_advanced`，不把 monorepo 的无关提交视为 Skill 更新。执行 update 前仍需按 `AGENTS.md` 阅读实际 diff 并取得明确选择。

## 仓库开发

`.agents/skills/` 与 `.claude/skills/` 各检入 11 个相对目录软链接，全部指向 default base，供仓库自身迭代；安装器不管理这些链接。仓库不创建 `.codex/skills` 或 `.pi/skills`。

主要验证命令：

```bash
python -B scripts/check-plugins.py
python -B -m unittest discover -s plugins/with-agents/tests

cd plugins/task/core
uv lock --check
uv run --frozen ruff check src tests
uv run --frozen mypy src
uv run --frozen pytest
cd ..
uv run --project core scripts/build-package.py

uvx pre-commit run --all-files
```

`scripts/check-plugins.py` 是结构校验命令，不是 test suite。仓库根不保留 `tests/`；with-agents 和 Task Core 的插件局部测试继续保留。
