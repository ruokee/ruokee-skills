# Primitive Obsession

## 它是什么

Primitive Obsession 指的是用原始基本类型 - 字符串、整数、浮点数、裸 tuple 和未标注类型的 dictionary - 去表示本该由专门类型承载的领域概念。用户 ID “只是个字符串”，金额 “只是个浮点数”，订单状态 “只是这些字符串值中的一个”，坐标 “只是两个数字的 tuple”，解析后的记录 “只是一个 `dict[str, Any]`”。每一个决定单看都方便，但合在一起，会把领域从代码里抹掉。

代价在于 primitive 没有意义，也不会强制规则。一个接收 `(str, str, str)` 的函数，根本帮不了调用方记住哪个字符串是 email、哪个是 name、哪个是 city - 也挡不住它们顺序传错。用 `float` 表示 money，会让它很自然地又被拿去跟别的单位的数量相乘。状态如果只是字符串，就可能悄悄出现 `"shippped"` 这种拼写错误，直到生产环境才被发现。类型系统本来可以抓住这些错误，但现在它什么都没被告知。

## 信号

- **验证散落在调用点。** 同样的 `if not re.match(EMAIL_RE, value)` 在每个收到 email 字符串的地方都要写一遍，因为字符串本身并没有保证任何东西。value object 会在构造时一次性验证。
- **总是成组传递的 primitive。** 纬度和经度总是一起出现，`currency` 和 `amount_cents` 总是并排出现 - 这些 Data Clumps 就该合成一个类型。
- **字符串化的状态和类型。** 一个其实应该是枚举的字段，却以自由字符串存储，并在代码里到处和字符串字面量比较。
- **`dict[str, Any]` 充当伪记录。** 形状已知且固定的数据却被当成 dictionary 传来传去，每次访问都变成字符串键查找，类型检查器无法验证，拼写错一个键就运行时报错。
- **行为与类型绑定，却没有承载处。** 处理这个 primitive 的函数（格式化电话、规范化代码）全都散落成自由函数，因为根本没有一个类型可以挂载这些行为。

## 何时引入领域类型

当某个概念有自己的验证规则、不变量或相关行为时，引入一个 **value object**（在 Python 中可以是 `frozen` dataclass、`NamedTuple`，或者一个小 class） - 例如 money、email、date range、coordinate。当值属于一个固定已知集合时，引入 **enum**（`Enum`、`StrEnum`）；这能把拼写错误变成错误，并让你在 `match` 里获得穷尽性。当 `dict[str, Any]` 有已知形状时，引入 **typed record**（`dataclass`、`TypedDict`、Pydantic model） - 这样字段访问能被检查，结构也由类型文档化。

这样做的收益是集中化：验证在构造类型的边界处只做一次，不变量在任何使用该类型的地方都成立，行为也有了显而易见的归宿。非法状态变得不可表达，而不仅仅是不太可能。

## 什么时候 primitive 可以接受

领域类型并不是免费午餐 - 它们会增加定义、构造步骤和一层间接层 - 过度使用它们本身也是一种 smell。primitive 适合以下场景：

- **内部管道。** 循环索引、临时计数、局部累加器 - 这些确实只是数字，包成类型只会增加噪音而没有安全收益。
- **真正的通用代码。** 序列化器、缓存、通用容器或日志 helper，应该能处理 _任何_ 值，没有理由知道你的领域类型；primitive 和泛型在这里才是正确选择。
- **性能敏感路径。** 给大规模数值数组里的每个元素都包一层 value object，可能真的有成本。在热点数值代码里，primitive 数组（或者 NumPy dtype）才合适，领域含义则由别处说明。
- **这个概念没有规则也没有行为。** 如果一个字符串只是个从不验证、从不与固定集合比较、也从不参与运算的 opaque label，那一个 `NewType` 别名可能已经够清楚了 - 甚至什么都不用也行。

判断标准在于这个概念 _值不值得_ 拥有自己的类型：包一层是否能防住一类错误、集中一条规则，或者为行为提供归宿？如果能，就引入类型；如果只是增加仪式感，就保留 primitive。

## 在 Python 中

- `dataclass(frozen=True)` 是默认的 value object：不可变、可比较、定义成本低。
- `StrEnum` / `IntEnum` 适合那些在边界处（序列化、存储）还需要 primitive 表示的固定集合。
- `TypedDict` 适合你必须保留 dict 形状（例如 API 边界上的 JSON），但又希望字段名被检查的情况。
- `NewType` 适合你想要一个零运行时开销的区分别名，希望类型检查器阻止 `UserId` 和 `OrderId` 互换，而不需要运行时 wrapper。
- 在系统边界（解析输入、读取数据库）构造领域类型，让 typed core 不再接触 raw primitive，这与 functional-core / imperative-shell 的划分一致。

Primitive Obsession 常常和 [feature-envy.md](./feature-envy.md)（行为嫉妒一个它无法附着的 primitive）以及 Data Clumps 同时出现；引入缺失的类型往往能一次解决好几个 smell。
