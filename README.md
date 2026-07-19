# ruokee-skills

Ruokee 的个人 Skills 工作仓库。

这个仓库用于管理 Skill Workspace、可安装的 Skill 产物、第三方 Skill 说明，以及后续的安装和版本切换工具。

## 顶层目录

```text
public/
experimential/
fork/
third-party/
```

- `public/`：自研且已经稳定到可以对外发布的 Skills。
- `experimential/`：自研或改造中、尚未正式可用的 Skills。
- `fork/`：基于外部 Skill 修改并由本仓库继续维护的分叉。
- `third-party/`：外部引入的 Skills。通常只保留极简 Workspace，并在 `README.md` 中说明来源和选用原因。

## Workspace 结构

Workspace 以 Skill 名称命名。一个最小的 Skill 结构如下：

```text
<domain>/<skill-name>/
├── <skill-name>/
├── README.md
└── upstream.toml  # third-party/fork 必须
```

带有语言变体的 Skill 结构如下：

```text
<domain>/<skill-name>/
├── en/
│   └── <skill-name>/
├── zh/
│   └── <skill-name>/
└── README.md
```

- `README.md` 和可安装的 Skill 产物目录是必须项。
- 可安装的 Skill 产物目录名称必须与 Skill 名称完全一致，例如 `zh/code-quality/`。
- `CHANGELOG.md`、`design.md`、`architecture.md`、`research/` 等维护材料按需添加。
- 语言变体由后续安装脚本选择或切换；同一个安装目标下同一时间只安装一个同名 Skill 变体。

## 上游版本管理

`third-party/` 和 `fork/` 下的 Workspace 必须包含 `upstream.toml`，记录上游 GitHub 仓库、目录、ref、锁定 commit、首次引入日期和最近更新日期。`update.managed_paths` 明确本地哪些文件由上游托管；本仓库独有文件不要列入。

一键检查全部 Skill：

```bash
scripts/check-skill-updates.py
```

检查以 `managed_paths` 的实际内容差异为准。上游仓库 ref 已推进、但托管文件未变化时，脚本报告“无内容更新”，不把 monorepo 中的无关提交误报为 Skill 更新。

查看某个 Skill 从锁定 commit 到当前上游 ref 的实际变更：

```bash
scripts/check-skill-updates.py diff <skill-name>
```

确认变更摘要并选定更新项后，再执行：

```bash
scripts/check-skill-updates.py update <skill-name> [<skill-name> ...]
```

`third-party` Skill 的上游托管文件直接替换；`fork` Skill 使用锁定版本、本地版本和最新上游版本进行三方合并。合并冲突时脚本停止，并且不会更新该 Skill 的文件或锁定 commit。
