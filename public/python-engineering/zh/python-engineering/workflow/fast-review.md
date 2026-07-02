# Fast Review — Python Engineering

默认模式。适用于开发后的快速、高信号自检，或较小 diff。以较低成本、较少且更有把握的 findings 为目标，而不是追求覆盖面。

## 触发条件

- 未指定模式时的默认选择。
- 日常开发自检。
- 小 diff、单文件，或聚焦的 PR。

## 前提

- 只读。不要修改代码。
- 需要一个明确目标：一个 diff、一个文件，或一组已命名的文件。如果范围是整个 repository，或者不清楚，就请用户收窄，或者按 full review 处理。

## 步骤

1. 建立项目事实。读取 `pyproject.toml`，看 `requires-python`、依赖和工具配置。快速扫一眼目录布局（`git ls-files`、`find`）来分类 project shape。
2. 读取偏好（如存在）：`.agents/preferences/python-engineering.md`，否则 `.agents/preferences/python-engineering/index.md`。如果都没有，就继续。
3. 扫描 diff 或指定文件。优先使用 `git diff`、`git show`、`rg`、`nl`，不要一次性加载全部内容。
4. 按以下方面检查目标：
    - 版本兼容性 - `requires-python` 与语法 / stdlib 的对应。
    - 依赖卫生 - 新 import 是否有声明依赖支持，是否放在正确分组。
    - 布局清晰度 - 文件是否放在适合项目形态的位置。
    - 类型边界泄漏 - `Any`、未受保护的 `cast`、模块边缘未标注的 public signature。
    - 资源生命周期 - 未用 context manager 或未保证清理就打开的文件、socket、lock、client。
    - 数据模型清晰度 - 用 dict / tuple 代替稳定记录，而不是改用 `dataclass` / `TypedDict`。
    - 不必要的复杂度 - 抽象、间接层或标志位超出了变更所需。
    - 工具可验证动作 - 写出能确认修复的命令（test、type check），但不要主动运行。
5. 输出 0-5 条 findings，按信号强度排序。零 findings 也是合理且好的结果。

## 输出格式

以 findings 为先，且保持简洁。每条 finding 一段：

```text
- [severity] path:line Title
  Fact: observable code/config evidence.
  Impact: correctness, maintainability, readability, testability, runtime, or delivery cost.
  Recommendation: smallest sufficient change.
```

除非真的有信号，否则省略 Open Questions 和 Notes。不要为了凑足五条而填充内容。

## 停止规则

- 不要升级到 full review - 只有当 diff 明显值得更深检查时才建议。
- 不要修改代码。
- 不要运行修复、安装，或任何会写文件、创建 `.venv` / 缓存、或改变 lockfile 的命令。
- 最多 5 条 findings；保留最有分量的。
- 跳过 Ruff、ty、mypy 或 pre-commit 能机械捕捉到的内容。如果它们会影响 review，可在 Note 中提一次。
- 不要把偏好当作 Python 语言事实。
