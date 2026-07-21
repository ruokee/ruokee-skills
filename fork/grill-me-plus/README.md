# grill-me-plus

基于 Matt Pocock 的 `grilling` 与实验性 `batch-grill-me` 改造的批量决策访谈 Skill。它通过依赖感知的问题轮次压力测试计划、决定或想法，正常轮次提出三个当前可以独立回答的高价值问题。

## 来源

- 上游仓库：https://github.com/mattpocock/skills
- 主要跟踪路径：`skills/in-progress/batch-grill-me`
- 同时参考：`skills/productivity/grilling`
- 引入 commit：`9603c1cc8118d08bc1b3bf34cf714f62178dea3b`
- 引入日期：2026-07-21
- 许可证：MIT，完整条款随两个语言变体分别保留在 `LICENSE.txt`

## 改造内容

- 将单问题访谈和“询问整个 frontier”调整为正常轮次三个无相互依赖的问题，依赖不足时减少。
- 在可问问题超过三个时，优先处理改变方向、高风险、难撤销或能解除最多下游依赖的决定。
- 由 Agent 自行调查可获得的事实，不把子代理作为运行环境的硬依赖。
- 集中确认低风险、可撤销的默认项，但不把高影响决定隐藏在默认项中。
- 用户深入讨论、质疑建议或提出疑问时暂停问题队列，先解决当前讨论，再重算决策树并恢复访谈。
- 正常轮次提出三个独立高价值问题；依赖不足时减少问题，讨论结束后恢复批量提问。
- 增加阶段总结、上游决定变更后的结论失效处理，以及不会阻碍下一步的停止条件。
- 保留最终确认前不实施的边界，并允许用户明确要求边决策边行动。

## 语言变体

```text
fork/grill-me-plus/
├── en/
│   └── grill-me-plus/
├── zh/
│   └── grill-me-plus/
├── README.md
└── upstream.toml
```

- `en/grill-me-plus/` 是英文源版本，也是非中文 locale 下的默认安装变体。
- `zh/grill-me-plus/` 是由英文版本翻译的中文审计版本，保持相同的结构和行为。
- 需要明确选择中文版本时，使用 `uv run scripts/install.py install grill-me-plus --variant zh`。

本 Skill 禁止隐式调用，避免普通方案讨论意外进入持续追问模式。
