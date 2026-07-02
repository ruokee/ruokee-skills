# Tooling References

当任务涉及选择、配置或推理某个 Python 工具时，阅读这些文件。每份文档都会说明这个工具做什么、处于工作流中的什么位置，以及它的职责边界在哪里。

这些工具分成几层：环境与依赖（uv）、格式化与 lint（ruff）、类型检查（ty、mypy、basedpyright）、测试与 coverage（pytest、coverage）、提交门禁（pre-commit），以及项目专属 lint 扩展（flake8-plugin）。

- [uv.md](uv.md)：项目、依赖、lockfile、脚本和 Python 版本管理器。
- [ruff.md](ruff.md)：formatter 和 linter，它会自动修复什么，以及会把什么留给 review。
- [ty.md](ty.md)：快速的 Rust-based type checker，它在速度与成熟度之间的取舍。
- [mypy.md](mypy.md)：成熟的 strict type checker、plugin、渐进式采用。
- [basedpyright.md](basedpyright.md)：更严格的 Pyright 社区分支、IDE 集成。
- [pytest.md](pytest.md)：测试发现、fixtures、parametrization、import mode。
- [coverage.md](coverage.md)：branch coverage、阈值，以及 coverage 能做什么、不能证明什么。
- [pre-commit.md](pre-commit.md)：本地 hook 框架、快速提交门禁、可选 CI 用法。
- [flake8-plugin.md](flake8-plugin.md)：基于 AST 的项目专属规则插件机制。

没有任何单一工具能保证质量。每个工具只衡量狭窄的一部分；正确性仍然来自测试、review 和设计。
