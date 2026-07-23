---
name: msgspec
description: This skill should be used when the user asks to "使用 msgspec", "msgspec 序列化", "msgspec 验证", "定义 Struct", "msgspec 编码", "msgspec 解码", "标签联合", mentions "msgspec.Struct", "msgspec.json.encode", "msgspec.field", or needs guidance on msgspec usage patterns, type validation, and serialization in Python. Provides comprehensive msgspec documentation in Chinese.
---

# msgspec

msgspec 是一个高性能的 Python 序列化和验证库。在需要以下场景时使用 msgspec：

## 适用场景

- 需要高性能序列化（比 `Pydantic` 快 10-50 倍，比 `dataclasses` 快 5-20 倍）
- 需要多协议支持（JSON、MessagePack、YAML、TOML）
- 需要类型安全的数据结构定义和自动验证
- 需要替代 `Pydantic` 以提升性能，同时保持类型验证功能
- 需要比 `dataclasses` 更强大的序列化能力
- 希望核心功能无需第三方依赖的轻量级方案

## 快速参考

**安装**

```shell
# 基础安装（包含 JSON 和 MessagePack 支持）
uv add msgspec

# 安装额外协议支持
uv add msgspec[yaml]      # YAML 支持
uv add msgspec[toml]      # TOML 支持
uv add msgspec[yaml,toml] # 安装所有额外协议
```

**常用模式速查**

```python
# 基本结构体
class Basic(msgspec.Struct):
    field: Annotated[str, msgspec.Meta(description="字段描述")]

# 带默认值
class WithDefaults(msgspec.Struct):
    immutable_default: str = "default"
    mutable_default: list[str] = msgspec.field(default_factory=list)
    optional_field: str | None = None
    ignoreable_field: str | msgspec.UnsetType = msgspec.UNSET

# 不可变结构体
class Immutable(msgspec.Struct, frozen=True):
    x: float
    y: float

# 关键字参数
class KeywordOnly(msgspec.Struct, kw_only=True):
    field1: str
    field2: int

# 标签联合
class VariantA(msgspec.Struct, tag="a"):
    type: ClassVar[Literal["a"]] = "a"
    data: str

class VariantB(msgspec.Struct, tag="b"):
    type: ClassVar[Literal["b"]] = "b"
    value: int

type Union = VariantA | VariantB

# 约束
class Constrained(msgspec.Struct):
    limited_str: Annotated[str, msgspec.Meta(min_length=1, max_length=100)]
    positive_int: Annotated[int, msgspec.Meta(gt=0)]
    email: Annotated[str, msgspec.Meta(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")]

# 字段重命名
class APIModel(msgspec.Struct, rename="camel"):  # snake_case -> camelCase
    user_id: int
    first_name: str

# 序列化/反序列化
user = User(name="Alice", age=30)
encoded = msgspec.json.encode(user)  # 编码
decoded = msgspec.json.decode(encoded, type=User)  # 解码
```

## 最佳实践与常见陷阱

### 1. 可变类型默认值

**✓ 推荐做法**：永远使用 `msgspec.field(default_factory=...)` 来设置可变类型的默认值。

```python
class User(msgspec.Struct):
    name: str
    tags: list[str] = msgspec.field(default_factory=list)
    metadata: dict[str, str] = msgspec.field(default_factory=dict)
```

**✗ 常见错误**：直接使用可变对象（如 `[]` 或 `{}`）作为默认值会导致所有实例共享同一个对象。

```python
class User(msgspec.Struct):
    name: str
    tags: list[str] = []  # 危险！

user1 = User(name="Alice")
user1.tags.append("admin")

user2 = User(name="Bob")
print(user2.tags)  # ["admin"] - 糟糕！共享了列表
```

### 2. 字段顺序

**✓ 推荐做法**：

**方案1：必选字段在前，可选字段在后**

```python
class User(msgspec.Struct):
    name: str
    role: str = "user"
```

**方案2：使用 kw_only 允许任意顺序**

```python
class User(msgspec.Struct, kw_only=True):
    role: str = "user"
    name: str  # 现在可以放在后面
```

**✗ 常见错误**：带默认值的字段排在必选字段之前会导致 `SyntaxError`。

```python
# SyntaxError: non-default argument follows default argument
class User(msgspec.Struct):
    role: str = "user"  # 有默认值
    name: str  # 必选字段
```

### 3. 标签联合（Tagged Unions）

**✓ 推荐做法**：当有多种可能的数据结构时，使用标签联合来明确区分类型。

```python
class SuccessResponse(msgspec.Struct, tag="success"):
    type: ClassVar[Literal["success"]] = "success"
    data: Annotated[dict, msgspec.Meta(description="响应数据")]

class ErrorResponse(msgspec.Struct, tag="error"):
    type: ClassVar[Literal["error"]] = "error"
    message: Annotated[str, msgspec.Meta(description="错误消息")]
    code: Annotated[int, msgspec.Meta(description="错误代码")]

type Response = SuccessResponse | ErrorResponse
```

**✗ 不推荐**：使用嵌套的可选字段会导致结构混乱。

```python
class Response(msgspec.Struct):
    success: bool
    data: dict | None = None
    message: str | None = None
    code: int | None = None
```

**✗ 常见错误**：忘记为 `Union` 类型添加标签会导致反序列化时无法正确区分类型。

```python
class Dog(msgspec.Struct):
    name: str
    breed: str

class Cat(msgspec.Struct):
    name: str
    lives: int

type Animal = Dog | Cat

# 反序列化时无法区分
data = b'{"name":"Fluffy","breed":"Husky"}'
decoder = msgspec.json.Decoder(type=Animal)
animal = decoder.decode(data)  # 不确定性！可能被解析为 Dog 或 Cat
```

### 4. 其他情形

参考：[最佳实践与常见陷阱](references/best-practices.md)
- 类型注解，L5-21
- 可变类型默认值，L23-46
- 字段顺序，L48-75
- 不可变数据（frozen），L77-107
- 重用编码器/解码器，L109-146
- 约束验证，L148-178
- 标签联合，L180-224
- 自定义类型转换，L226-280
- 其他建议，L282-313

## 详细文档索引

[支持的类型](references/supported-types.md)
- msgspec 原生支持的所有类型

[序列化详解](references/serialization.md)
- 多协议支持 (JSON/MessagePack/YAML/TOML)，L3-12
- 基本用法，L14-30
- 协议切换，L32-58
- 编码器和解码器，L60-131
  - 重用编码器/解码器，L74-85
  - JSONL 格式，L87-105
  - 编解码选项，L107-131
- 自定义类型处理，L133-165
- 流式处理，L167-181

[Struct 详解](references/struct.md)
- 初始化与 `__post_init__` 钩子，L5-12
- 基本字段定义，L13-37
- 默认值字段，L38-61
- 特殊类型（UNSET 类型），L62-96
- 字段顺序，L97-127
- 类变量，L128-155
- 字段重命名，L156-193
- 继承，L194-235
- 比较和哈希，L236-292
- 联合类型（Tagged Unions），L293-343
- 嵌套结构体，L344-363
- 结构体选项，L364-452
- 类型验证，L453-462

[验证与约束](references/validation.md)
- 支持的约束类型，L41-138
  - 字符串约束，L43-66
  - 数值约束，L68-92
  - 集合约束，L94-115
  - 通用元数据，L117-138
- 约束组合，L140-174
- 自定义验证，L176-201
- 验证错误处理，L203-221
- 验证时机，L223-244

[转换器详解](references/converters.md)
- 编码钩子（`enc_hook`），L11-84
  - 基本用法，L13-34
  - 多类型处理，L36-64
  - 自定义类型编码，L66-84
- 解码钩子（`dec_hook`），L86-167
  - 基本用法，L88-107
  - 类型化解码，L109-129
  - 多类型解码，L131-151
  - 自定义类型解码，L153-167
- 完整示例，L169-225
- `msgspec.convert` 函数，L227-353
  - 基本用法，L229-249
  - 字典到 `Struct` 转换，L251-267
  - 带钩子的转换，L269-294
  - ORM 对象转换，L296-352
- 高级技巧，L354-426
  - 条件编码，L356-368
  - 嵌套自定义类型，L370-398
  - 版本兼容性处理，L400-413
  - 错误处理和回退，L415-426

[对比分析](references/comparison.md)
- msgspec VS Pydantic，L5-20
- msgspec VS dataclasses，L22-36

## 完整示例代码

`examples/` 目录包含完整可运行的示例程序，展示 msgspec 的实际应用：

- [基础功能演示](examples/basic_usage.py)
  - Struct 定义和初始化
  - 默认值处理（不可变和可变类型）
  - 不可变 Struct (frozen)
  - 关键字参数 (kw_only)
  - 类型验证和错误处理
  - 多协议支持（JSON、MessagePack、YAML、TOML）

- [标签联合完整示例](examples/tagged_union.py)
  - API 响应处理（成功/失败）
  - 事件系统设计
  - 多态
  - 类型安全验证
  - 模式匹配应用

- [自定义类型转换](examples/custom_conversion.py)
  - 编码钩子 (enc_hook) 和解码钩子 (dec_hook)
  - 日期时间类型处理
  - 枚举类型转换
  - 路径类型处理
  - msgspec.convert 函数应用
  - ORM 对象转换
  - 性能优化技巧

运行示例：

```shell
# 运行基础示例
uv run examples/basic_usage.py

# 运行标签联合示例
uv run examples/tagged_union.py

# 运行自定义转换示例
uv run examples/custom_conversion.py
```

## 参考资源

- [msgspec 官方文档](https://jcristharif.com/msgspec/)
- [msgspec 使用指南](https://jcristharif.com/msgspec/usage.html)
- [msgspec Structs 详解](https://jcristharif.com/msgspec/structs.html)
- [msgspec 性能测试](https://jcristharif.com/msgspec/benchmarks.html)
- [msgspec GitHub 仓库](https://github.com/jcrist/msgspec)
