# Agentic Coding

关于 AI agent 配置质量的参考文档——也就是塑造 agent 行为的那些文件：`AGENTS.md`、`CLAUDE.md`、SKILL 文件、prompt rules、permission manifests 以及 workflow docs。这里关注的是配置表面，而不是 agent 产出的代码。产出代码里的 smell（长函数、重复知识、thin wrapper、投机性泛化）属于 `../refactoring/` 和 `../design-principles/`；这个目录讨论的是最初驱动 agent 的那些指令、上下文和引用。

前提是：agent 的配置本身也是一个工程产物，也有自己的失效模式。context 是有预算的，指令会互相冲突，引用会失效，模板会老化。这些问题会悄悄降低 agent 表现——agent 仍然在运行，只是它推理所依据的输入更嘈杂或更陈旧——因此它们也需要像生产代码一样被认真 review。

所有内容都放在一个文档里：[config-smells.md](./config-smells.md)。它把每种失效模式都视作 Fowler 意义上的 smell——一种值得调查的表面症状，而不是自动判死刑的缺陷。只要你在 review 或编写任何面向 agent 的配置，就应路由到这里。
