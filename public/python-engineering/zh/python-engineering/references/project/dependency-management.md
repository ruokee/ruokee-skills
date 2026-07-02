# Dependency Management

每个 dependency 既是便利，也是长期负担：它必须被解析、锁定、安装、审计，并最终升级；而且每增加一个 dependency，项目可能出错的表面积就会扩大。dependency management 的职责是声明每个 dependency _属于哪里_、_为什么存在_、_约束有多紧_，以及 _是否锁定了完整解析结果_。目标是在必须的地方可复现、在每个 use case 上尽量精简，并且如实区分哪些是运行时真正需要的，哪些只是开发者需要的。

## 运行时、开发、可选和 workspace 内部

任何 dependency 的第一步，是判断它属于哪个桶，因为不同的桶面向不同受众。

运行时 dependencies 放在 `[project.dependencies]`。它们是 package 没有它就无法 import 或运行的库 - 每个最终用户和每个部署都会安装它们。进入标准必须是真正必要：package 确实离不开它，而且自己重写它并不合理。

开发 dependencies - linters、formatters、type checkers、pytest、coverage、docs builders - 只在项目开发期间需要，运行时不需要。它们应放在 `[dependency-groups]`（PEP 735）下，通常按 `dev`、`test`、`docs` 等逻辑分组。把它们排除在 runtime 集合之外，才能避免部署中的服务拉入一个永远不会调用的测试框架。

可选 dependencies 放在 `[project.optional-dependencies]` 中，用于并非每个用户都需要的功能 - 数据库驱动、YAML parser、docs extra。每个 extra 都应对应一个清晰的功能边界，供用户按名称选择安装（`pip install mypkg[redis]`），而不是变成“有些人可能想要的东西”的垃圾桶。

workspace 内部 dependencies 是 workspace 各成员之间的边（见 [workspace](structure.md)）：一个成员依赖同一仓库中的另一个成员。这些依赖应遵循声明的依赖 _方向_，并且必须指向成员稳定的 public API，绝不能越界到其 internals。

## lockfile 策略

lockfile 记录的是精确的已解析图 - 每个 transitive package 的确切版本 - 因此安装结果可以逐字节复现。是否提交它，取决于项目 _是什么_，而不是某条普适规则。

应用和服务应该提交它们的 lockfile（`uv.lock` 或等价物），因为目标就是部署和测试完全一致的解析环境。CI 应当 _从_ lockfile 安装，以保证 production 与 development 一致。library 通常 _不_ 提交 lockfile：下游消费者会依据自己的约束来解析自己的图，而一个只在冻结解析上测试过的 library，会错过它实际声明支持的版本范围中的兼容性问题。workspace 使用单一 root lockfile 覆盖所有成员，每个成员自己的约束则写在各自的 `pyproject.toml` 中。

当 diff 中出现 lockfile 变更时，值得认真阅读而不是机械接受：意外的 major-version 跳升、新的 transitive dependency，或删除的 package，可能都随着不相关改动一起进入。升级应来自明确的命令和审查，而不是悄悄夹在其他编辑里漂移过去。

## 版本约束

每个约束的张力都在于灵活性和可复现性之间。compatible-release 约束（`>=2.1,<3` 或 `~=2.1`）允许 resolver 选择 patch 和 minor 更新，能让项目保持新鲜，并在与其他包并存时减少冲突 - 这对 library 是正确默认值，因为它的约束会传递给所有下游。exact pin（`==2.1.4`）保证一个特定版本，这正是应用部署时希望获得的可复现性；但放到 library 中就很不合群：它会把 pin 强加给每个消费者，也经常导致无法满足的解析。

一般规则是：只在安全的前提下尽量放宽约束。只在可复现性是目标时才精确 pin（应用场景尽量通过 lockfile，而不是通过 spec 本身）；在包会与其他包组合时使用 compatible ranges（library）。比必要更紧的 pin 应当附带理由，因为未来读者否则只能猜它是在防范真实不兼容，还是仅仅是过时的谨慎。

## 重量与正当性

每新增一个 dependency 都应通过一个正当性门槛：这个需求能否由标准库、更小的 library，或几行本地代码满足？标准库是默认 dependency；只有当 stdlib 机制确实不够时才越过它。为了一个小工具函数引入一个沉重 framework，换来的是更大的安装体积、更大的攻击面，以及持续的升级负担，而其实一个短小 helper 就能覆盖。

成本不止是下载大小。每个 dependency 都意味着一项供应链条目、一份许可证检查和一份维护承诺 - 一个无人维护或维护薄弱的 package 一旦停止修复，就会变成项目自己的问题。有些重量是不可避免且正确的：数值和数据处理确实需要大型且维护良好的 package，这并不是坏味道。判断标准是比例是否合适，而不是为了极简而极简。

## 单仓库中的依赖方向

在 workspace 或 monorepo 中，内部 packages 之间的 dependencies 形成一张 graph，而这张 graph 必须保持有向无环。共享且更底层的 packages（领域模型、工具函数）是被依赖的；applications 和 services 依赖它们，而不是反过来。当两个成员开始互相 import 时，它们之间的边界就已经失效，本质上是一个 package 只是穿了两个名字。

每个成员都应只声明自己的直接 dependencies。某个成员如果只是因为另一个成员碰巧引入了某个 package，就把它当作 transitive dependency 来使用，那么它就存在一个未声明的 dependency；一旦中介不再引入它，代码就会立刻出问题。显式的逐成员声明，再加上单一共享 lockfile，正是让 workspace 保持一致而不是放大耦合的基础；这一点的结构侧内容见 [structure](structure.md)。
