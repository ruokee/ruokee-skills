# Abstract Factory

## 目的

创建必须一起使用的一组相关对象，而不让调用方耦合到具体类。调用方选择一个工厂；它产出的所有对象都保证属于同一组匹配的集合。

## 解决的问题

有些对象只有成组使用才有意义。S3 reader 要配 S3 writer；深色主题的按钮要配深色主题的菜单；Postgres connection 要配 Postgres dialect 和 migration runner。若调用方逐个组装这些部件，就无法阻止把 Postgres reader 和 SQLite writer 混在一起。Abstract Factory 把“家族”变成选择单位：只选一次后端，它返回的每个 product 都是一致的。

这就是它的区别约束。[factory.md](factory.md) 解决的是“我要构建哪个具体类？”Abstract Factory 解决的是“我要构建哪一整套彼此兼容的类？”

## 结构与参与者

- **抽象工厂**：为家族中的每个 product 声明创建方法（`make_reader`、`make_writer`）。
- **具体工厂**：每个家族一个（`S3Storage`、`LocalStorage`），各自生成自己变体中的 product。
- **抽象 product**：调用方依赖的接口（`Reader`、`Writer`）。
- **具体 product**：家族特定实现。

调用方持有一个抽象工厂并调用它的创建方法；它从不直接命名具体 product。

## 何时使用

- 一整套 product 必须一起切换：UI toolkit 主题、数据库后端、云厂商客户端、传输栈。
- 多个对象必须共享相同的配置、凭据或生命周期，而且混用变体会出错。
- 测试需要把一整组依赖（例如一个假的 storage 家族）替换成真实实现。

## 何时不要用

- 只有一个 product，或者只有一个家族。那你只需要一个 [factory.md](factory.md)，或者直接用普通构造函数。
- “家族”约束并不真实。product 其实不必匹配，把它们分组只会增加仪式感，却不能防住任何错误。
- 它悄悄膨胀成一个通用 service locator，按需构建任何东西，失去了当初支撑它的“家族一致性”保证。

## Python 习惯写法

`Protocol` 加一个选择函数，通常就能表达整个模式，而不必造出一片接口森林：

```python
class StorageBackend(Protocol):
    def make_reader(self) -> Reader: ...
    def make_writer(self) -> Writer: ...


def build_storage(profile: StorageProfile) -> StorageBackend:
    if profile.kind == "s3":
        return S3Storage(profile)
    return LocalStorage(profile)
```

其他更符合 Python 习惯的形态：

- **把模块当工厂**：一个 `s3_backend` 模块和一个 `local_backend` 模块，各自暴露 `make_reader` / `make_writer`，在 composition root 里通过导入正确模块来选择。
- **dataclass profile**：把家族共享配置装进一个冻结对象，再传给每个 product。
- **composition root**：启动时一次性组装匹配的一套对象并注入它，而不是把工厂调用散落各处。

避免照搬 Java 那套抽象基类分层。Duck typing 和 `Protocol` 能通过结构获得同样的保证，而不需要名义继承。

## 失效模式

- 一个为单一家族而生的工厂对象、抽象 product 和具体 product 树，纯属额外开销。
- 家族边界模糊，导致工厂不断累积无关的创建方法，最后变成 god object。
- product 悄悄去读全局状态，而不是使用工厂共享配置，破坏了该模式要维护的一致性保证。

## 与其他模式的关系

Abstract Factory 是把 [factory.md](factory.md) 从单个 product 扩展到一组协调一致的家族。它的 product 常常会借助 [builder.md](builder.md) 来完成复杂构造。工厂选择经常和为整个子系统选择一个 [strategy.md](strategy.md) 同时发生。当一组对象还需要一个简化的组合入口时，可以把它包在 [facade.md](facade.md) 后面。
