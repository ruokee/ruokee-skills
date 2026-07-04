---
name: msgspec
description: This skill should be used when the user asks to "use msgspec", "msgspec serialization", "msgspec validation", "define Struct", "msgspec encode", "msgspec decode", "tagged unions", mentions "msgspec.Struct", "msgspec.json.encode", "msgspec.field", or needs guidance on msgspec usage patterns, type validation, and serialization in Python. Provides comprehensive msgspec documentation.
---

# msgspec

msgspec is a high-performance Python serialization and validation library. Use msgspec in the following scenarios:

## Use Cases

- High-performance serialization needs (10-50x faster than `Pydantic`, 5-20x faster than `dataclasses`)
- Multi-protocol support (JSON, MessagePack, YAML, TOML)
- Type-safe data structure definition with automatic validation
- Replacing `Pydantic` for better performance while maintaining type validation
- More powerful serialization than `dataclasses`
- Lightweight solution with no third-party dependencies for core functionality

## Quick Reference

**Installation**

```shell
# Basic installation (includes JSON and MessagePack support)
uv add msgspec

# Install with extra protocol support
uv add msgspec[yaml]      # YAML support
uv add msgspec[toml]      # TOML support
uv add msgspec[yaml,toml] # All extra protocols
```

**Common Patterns**

```python
# Basic struct
class Basic(msgspec.Struct):
    field: Annotated[str, msgspec.Meta(description="Field description")]

# With defaults
class WithDefaults(msgspec.Struct):
    immutable_default: str = "default"
    mutable_default: list[str] = msgspec.field(default_factory=list)
    optional_field: str | None = None
    ignoreable_field: str | msgspec.UnsetType = msgspec.UNSET

# Frozen struct
class Immutable(msgspec.Struct, frozen=True):
    x: float
    y: float

# Keyword-only arguments
class KeywordOnly(msgspec.Struct, kw_only=True):
    field1: str
    field2: int

# Tagged unions
class VariantA(msgspec.Struct, tag="a"):
    type: ClassVar[Literal["a"]] = "a"
    data: str

class VariantB(msgspec.Struct, tag="b"):
    type: ClassVar[Literal["b"]] = "b"
    value: int

type Union = VariantA | VariantB

# Constraints
class Constrained(msgspec.Struct):
    limited_str: Annotated[str, msgspec.Meta(min_length=1, max_length=100)]
    positive_int: Annotated[int, msgspec.Meta(gt=0)]
    email: Annotated[str, msgspec.Meta(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")]

# Field renaming
class APIModel(msgspec.Struct, rename="camel"):  # snake_case -> camelCase
    user_id: int
    first_name: str

# Serialization/Deserialization
user = User(name="Alice", age=30)
encoded = msgspec.json.encode(user)  # Encode
decoded = msgspec.json.decode(encoded, type=User)  # Decode
```

## Best Practices and Common Pitfalls

### 1. Mutable Default Values

**✓ Recommended**: Always use `msgspec.field(default_factory=...)` for mutable default values.

```python
class User(msgspec.Struct):
    name: str
    tags: list[str] = msgspec.field(default_factory=list)
    metadata: dict[str, str] = msgspec.field(default_factory=dict)
```

**✗ Common Mistake**: Using mutable objects (like `[]` or `{}`) directly as defaults causes all instances to share the same object.

```python
class User(msgspec.Struct):
    name: str
    tags: list[str] = []  # Dangerous!

user1 = User(name="Alice")
user1.tags.append("admin")

user2 = User(name="Bob")
print(user2.tags)  # ["admin"] - Oops! Shared list
```

### 2. Field Order

**✓ Recommended**:

**Option 1: Required fields first, optional fields last**

```python
class User(msgspec.Struct):
    name: str
    role: str = "user"
```

**Option 2: Use kw_only to allow any order**

```python
class User(msgspec.Struct, kw_only=True):
    role: str = "user"
    name: str  # Can now be placed after fields with defaults
```

**✗ Common Mistake**: Fields with defaults before required fields causes `SyntaxError`.

```python
# SyntaxError: non-default argument follows default argument
class User(msgspec.Struct):
    role: str = "user"  # Has default
    name: str  # Required field
```

### 3. Tagged Unions

**✓ Recommended**: Use tagged unions to distinguish between multiple data structures.

```python
class SuccessResponse(msgspec.Struct, tag="success"):
    type: ClassVar[Literal["success"]] = "success"
    data: Annotated[dict, msgspec.Meta(description="Response data")]

class ErrorResponse(msgspec.Struct, tag="error"):
    type: ClassVar[Literal["error"]] = "error"
    message: Annotated[str, msgspec.Meta(description="Error message")]
    code: Annotated[int, msgspec.Meta(description="Error code")]

type Response = SuccessResponse | ErrorResponse
```

**✗ Not Recommended**: Using nested optional fields leads to confusing structures.

```python
class Response(msgspec.Struct):
    success: bool
    data: dict | None = None
    message: str | None = None
    code: int | None = None
```

**✗ Common Mistake**: Forgetting to add tags to `Union` types prevents proper deserialization.

```python
class Dog(msgspec.Struct):
    name: str
    breed: str

class Cat(msgspec.Struct):
    name: str
    lives: int

type Animal = Dog | Cat

# Cannot distinguish during deserialization
data = b'{"name":"Fluffy","breed":"Husky"}'
decoder = msgspec.json.Decoder(type=Animal)
animal = decoder.decode(data)  # Ambiguous! Could be Dog or Cat
```

### 4. Other Scenarios

See: [Best Practices](references/best-practices.md)
- Type annotations, L5-22
- Mutable default values, L23-47
- Field order, L48-76
- Immutable data (frozen), L77-108
- Reusing encoders/decoders, L109-147
- Constraint validation, L148-181
- Tagged unions, L182-263
- Custom type conversion, L264-317
- Other recommendations, L406-503

## Detailed Documentation Index

[Supported Types](references/supported-types.md)
- All types natively supported by msgspec

[Serialization Guide](references/serialization.md)
- Multi-protocol support (JSON/MessagePack/YAML/TOML), L9-14
- Basic usage, L15-35
- Protocol switching, L36-57
- Encoders and decoders, L58-145
  - Reusing encoders/decoders, L76-96
  - JSONL format, L97-124
  - Encoding/decoding options, L125-145
- Custom type handling, L146-182
- Streaming, L183-204

[Struct Guide](references/struct.md)
- Initialization and `__post_init__` hook, L15-34
- Basic field definition, L35-58
- Default value fields, L59-93
- Special types (UNSET type), L94-134
- Field order, L135-163
- Class variables, L164-202
- Field renaming, L203-250
- Inheritance, L251-292
- Comparison and hashing, L293-342
- Union types (Tagged Unions), L343-393
- Nested structs, L394-427
- Struct options, L428-528
- Type validation, L529-549

[Validation and Constraints](references/validation.md)
- Supported constraint types, L58-211
  - String constraints, L60-99
  - Numeric constraints, L100-143
  - Collection constraints, L144-177
  - General metadata, L178-211
- Combining constraints, L212-267
- Custom validation, L268-304
- Validation error handling, L305-344
- Validation timing, L345-401

[Converters Guide](references/converters.md)
- Encoding hooks (`enc_hook`), L13-99
  - Basic usage, L19-39
  - Handling multiple types, L40-70
  - Custom type encoding, L71-99
- Decoding hooks (`dec_hook`), L100-193
  - Basic usage, L104-123
  - Typed decoding, L124-145
  - Multiple type decoding, L146-168
  - Custom type decoding, L169-193
- Complete examples, L194-271
- `msgspec.convert` function, L272-401
  - Basic usage, L276-296
  - Dict to `Struct` conversion, L297-327
  - Conversion with hooks, L328-349
  - ORM object conversion, L350-401
- Advanced techniques, L402-491
  - Conditional encoding, L404-419
  - Nested custom types, L420-460
  - Version compatibility, L461-474
  - Error handling and fallbacks, L475-491

[Comparison Analysis](references/comparison.md)
- msgspec VS Pydantic, L5-20
- msgspec VS dataclasses, L22-36

## Complete Example Code

The `examples/` directory contains complete runnable examples demonstrating msgspec in practice:

- [Basic Usage Demo](examples/basic_usage.py)
  - Struct definition and initialization
  - Default value handling (immutable and mutable types)
  - Frozen structs
  - Keyword-only arguments (kw_only)
  - Type validation and error handling
  - Multi-protocol support (JSON, MessagePack, YAML, TOML)

- [Tagged Union Complete Example](examples/tagged_union.py)
  - API response handling (success/failure)
  - Event system design
  - Polymorphism
  - Type-safe validation
  - Pattern matching applications

- [Custom Type Conversion](examples/custom_conversion.py)
  - Encoding hooks (enc_hook) and decoding hooks (dec_hook)
  - DateTime type handling
  - Enum type conversion
  - Path type handling
  - msgspec.convert function usage
  - ORM object conversion
  - Performance optimization tips

Run examples:

```shell
# Run basic example
uv run examples/basic_usage.py

# Run tagged union example
uv run examples/tagged_union.py

# Run custom conversion example
uv run examples/custom_conversion.py
```

## Reference Resources

- [msgspec Official Documentation](https://jcristharif.com/msgspec/)
- [msgspec Usage Guide](https://jcristharif.com/msgspec/usage.html)
- [msgspec Structs Guide](https://jcristharif.com/msgspec/structs.html)
- [msgspec Benchmarks](https://jcristharif.com/msgspec/benchmarks.html)
- [msgspec GitHub Repository](https://github.com/jcrist/msgspec)
