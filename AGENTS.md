# Project Agent Guidelines

ruokee-skills 是 Ruokee 的个人 Skills 工作仓库。

## Git Workflow

- Develop and fix code on a task branch. Reuse the branch for the same task; do not edit `main` directly.
- Commit each atomic task to its branch by default. Stage only files changed for that task, and leave unrelated or unknown changes untouched.
- Let `git commit` run the repository-level hooks, which cover baseline file hygiene and commit message validation but not each Skill's own checks. If hooks modify task files, restage and commit again; if they report another error, run the failing check to diagnose it.
- Before requesting review, commit all task changes and leave the related worktree clean so the user can review branch or commit diffs.
- A request to commit authorizes a branch commit only. Merging into `main` requires user review and explicit authorization.
- Squash-merge task branches into `main` and keep the branch. This applies even to single-commit branches; do not use plain merge, fast-forward merge, rebase-and-fast-forward, or direct ref movement.
- Worktree location: `./.worktrees`.

## Rules

- Let the editor handle soft wrapping. Do not hard-wrap strings to the screen width.
- Do not use `from __future__ import annotations`.
- Validate changed Skills and Packages with `plugins/code-quality` and any relevant component-specific checks.

## 上游 Skill 更新

当用户要求检查或更新 `plugins/*/meta.toml` 中带 `[upstream]` 的外部 Skill 时：

1. 运行 `scripts/check-skill-updates.py check --json` 检查全部上游。
2. 对每个状态为 `update_available` 的 Skill 运行 `scripts/check-skill-updates.py diff <skill-name>`，阅读实际 diff。`ref_advanced` 表示上游仓库有无关提交，不视为 Skill 内容更新。
3. 向用户总结行为变化、文件变化和 fork 的本地合并风险；没有实际变化也要明确说明。
4. 列出可更新项，让用户明确选择。未取得选择前不要执行更新。
5. 仅对选中项运行 `scripts/check-skill-updates.py update <skill-name>...`。
6. 检查本地 `git diff`，确认 fork 的本地扩展仍然存在，并验证改动后的 Skill。

新增外部 Skill 时，在插件根 `meta.toml` 中添加 `[upstream]`。`managed_paths` 相对 default Skill 根解析，只列由上游托管的文件，不包含本仓库独有文件。未经用户明确同意，不修改锁定 commit，也不扩大托管文件范围。
