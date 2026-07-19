# 项目约定

## 上游 Skill 更新

当用户要求检查或更新 `third-party/`、`fork/` 中引入的 Skill 时：

1. 运行 `scripts/check-skill-updates.py check --json` 检查全部上游。
2. 对每个状态为 `update_available` 的 Skill 运行 `scripts/check-skill-updates.py diff <skill-name>`，阅读实际 diff。`ref_advanced` 表示上游仓库有无关提交，不视为 Skill 内容更新。
3. 向用户总结行为变化、文件变化和 fork 的本地合并风险；没有实际变化也要明确说明。
4. 列出可更新项，让用户明确选择。未取得选择前不要执行更新。
5. 仅对选中项运行 `scripts/check-skill-updates.py update <skill-name>...`。
6. 检查本地 `git diff`，确认 fork 的本地扩展仍然存在，并验证改动后的 Skill。

新增外部 Skill 时，在 Workspace 根目录添加 `upstream.toml`。`managed_paths` 只列由上游托管的文件，不包含本仓库独有文件。未经用户明确同意，不修改锁定 commit，也不扩大托管文件范围。
