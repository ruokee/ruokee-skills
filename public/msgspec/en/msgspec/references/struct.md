# msgspec Struct Guide

This guide covers msgspec's `Struct` type, which provides a high-performance alternative to dataclasses and Pydantic models.

## Overview

[msgspec Structs Documentation](https://jcristharif.com/msgspec/structs.html)

`msgspec.Struct` is a typed data structure that combines:
- High-performance serialization (10-50x faster than Pydantic)
- Automatic type validation
- Clean, declarative syntax
- Multiple protocol support (JSON, MessagePack, YAML, TOML)

## Initialization and `__post_init__` Hook

Structs support a `__post_init__` method that runs after initialization:

```python
import msgspec

class User(msgspec.Struct):
    name: str
    age: int

    def __post_init__(self):
        """Validate after initialization"""
        if self.age < 0:
            raise ValueError(f"Age cannot be negative: {self.age}")

user = User(name="Alice", age=30)  # OK
# User(name="Bob", age=-5)  # Raises ValueError
```

## Basic Field Definition

Define fields with type annotations:

```python
from typing import Annotated
import msgspec

class Product(msgspec.Struct):
    """Product information"""

    name: Annotated[str, msgspec.Meta(description="Product name")]
    price: Annotated[float, msgspec.Meta(description="Price in USD", gt=0)]
    stock: Annotated[int, msgspec.Meta(description="Stock quantity", ge=0)]
    sku: Annotated[str, msgspec.Meta(description="SKU code", pattern=r"^[A-Z]{3}-\d{6}$")]
```

Benefits of `msgspec.Meta`:
- Self-documenting fields
- Automatic validation during deserialization
- No runtime overhead for validation
- Clear data quality requirements

## Default Value Fields

### Immutable Defaults

For immutable types (str, int, bool, None, etc.), use direct assignment:

```python
class Config(msgspec.Struct):
    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    timeout: float = 30.0
```

### Mutable Defaults

**CRITICAL**: For mutable types (list, dict, set), always use `msgspec.field(default_factory=...)`:

```python
class UserProfile(msgspec.Struct):
    name: str
    # ✓ Correct - each instance gets its own list
    tags: list[str] = msgspec.field(default_factory=list)
    metadata: dict[str, str] = msgspec.field(default_factory=dict)

    # ✗ WRONG - all instances share the same list!
    # tags: list[str] = []

user1 = UserProfile(name="Alice")
user1.tags.append("admin")

user2 = UserProfile(name="Bob")
print(user2.tags)  # [] - independent list, not ["admin"]
```

## Special Types (UNSET Type)

`msgspec.UNSET` represents a field that can be omitted during serialization:

```python
from typing import Annotated
import msgspec

class UserUpdate(msgspec.Struct):
    """Partial update struct"""

    name: str | msgspec.UnsetType = msgspec.UNSET
    email: str | msgspec.UnsetType = msgspec.UNSET
    age: int | msgspec.UnsetType = msgspec.UNSET

# Create partial update
update = UserUpdate(email="newemail@example.com")

# Encode - only email field is included
encoded = msgspec.json.encode(update)
print(encoded.decode())
# {"email":"newemail@example.com"}

# UNSET fields are omitted from serialization
```

**UNSET vs None**:
- `None`: Field is explicitly set to null value
- `UNSET`: Field is omitted entirely from serialization

```python
class Example(msgspec.Struct):
    optional: str | None = None
    ignoreable: str | msgspec.UnsetType = msgspec.UNSET

obj1 = Example(optional=None, ignoreable=msgspec.UNSET)
# {"optional":null}  - optional is included with null value

obj2 = Example(optional="value", ignoreable=msgspec.UNSET)
# {"optional":"value"}  - ignoreable is omitted
```

## Field Order

Fields without defaults must come before fields with defaults:

```python
# ✓ Correct
class User(msgspec.Struct):
    name: str          # Required field
    email: str         # Required field
    role: str = "user" # Optional field with default

# ✗ SyntaxError: non-default argument follows default argument
class BadUser(msgspec.Struct):
    role: str = "user"  # Has default
    name: str           # Required - ERROR!
```

**Solution**: Use `kw_only=True` to allow any field order:

```python
class User(msgspec.Struct, kw_only=True):
    role: str = "user"  # Can be first
    name: str           # Required field can be after defaults
    email: str

# Must use keyword arguments
user = User(name="Alice", email="alice@example.com")
```

## Class Variables

Use `typing.ClassVar` for class-level attributes:

```python
from typing import ClassVar, Literal
import msgspec

class APIResponse(msgspec.Struct):
    """API response with version info"""

    # Class variable - not serialized
    API_VERSION: ClassVar[str] = "v1"

    # Instance fields
    status: str
    data: dict

response = APIResponse(status="success", data={"id": 1})
encoded = msgspec.json.encode(response)
# {"status":"success","data":{"id":1}}
# API_VERSION is not included
```

**Use ClassVar with tagged unions**:

```python
class SuccessResponse(msgspec.Struct, tag="success"):
    type: ClassVar[Literal["success"]] = "success"
    data: dict

class ErrorResponse(msgspec.Struct, tag="error"):
    type: ClassVar[Literal["error"]] = "error"
    message: str
    code: int

type Response = SuccessResponse | ErrorResponse
```

## Field Renaming

The `rename` parameter converts field names during serialization:

```python
class UserAPI(msgspec.Struct, rename="camel"):
    """Python snake_case → JSON camelCase"""

    user_id: int
    first_name: str
    last_name: str
    email_address: str

user = UserAPI(
    user_id=1,
    first_name="Alice",
    last_name="Smith",
    email_address="alice@example.com"
)

encoded = msgspec.json.encode(user)
print(encoded.decode())
# {"userId":1,"firstName":"Alice","lastName":"Smith","emailAddress":"alice@example.com"}

# Decode also works
decoded = msgspec.json.decode(encoded, type=UserAPI)
print(decoded.first_name)  # "Alice"
```

**Available rename options**:
- `"camel"`: snake_case → camelCase
- `"pascal"`: snake_case → PascalCase
- `"kebab"`: snake_case → kebab-case
- Custom mapping: `rename={"python_field": "json_field"}`

**Custom field renaming**:

```python
class User(msgspec.Struct, rename={"user_id": "id", "email_address": "email"}):
    user_id: int
    email_address: str
    name: str  # Not renamed, stays as "name"

user = User(user_id=1, email_address="alice@example.com", name="Alice")
encoded = msgspec.json.encode(user)
# {"id":1,"email":"alice@example.com","name":"Alice"}
```

## Inheritance

Structs support single inheritance:

```python
class Person(msgspec.Struct):
    """Base struct"""
    name: str
    age: int

class Employee(Person):
    """Inherits from Person"""
    employee_id: int
    department: str

employee = Employee(
    name="Alice",
    age=30,
    employee_id=12345,
    department="Engineering"
)

# All fields are included
encoded = msgspec.json.encode(employee)
# {"name":"Alice","age":30,"employee_id":12345,"department":"Engineering"}
```

**Field order with inheritance**:

```python
class Base(msgspec.Struct):
    base_field: str = "default"

# ✗ ERROR: Required fields cannot follow optional fields from base class
class Child(Base):
    required_field: str  # SyntaxError!

# ✓ Solution: Use kw_only=True
class Child(Base, kw_only=True):
    required_field: str  # OK
```

## Comparison and Hashing

Structs support equality comparison by default:

```python
class Point(msgspec.Struct):
    x: float
    y: float

p1 = Point(x=1.0, y=2.0)
p2 = Point(x=1.0, y=2.0)
p3 = Point(x=3.0, y=4.0)

print(p1 == p2)  # True
print(p1 == p3)  # False
```

**Ordering comparison**: Not supported by default:

```python
# p1 < p2  # TypeError: '<' not supported

# Implement manually if needed
class Point(msgspec.Struct):
    x: float
    y: float

    def __lt__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return (self.x, self.y) < (other.x, other.y)
```

**Hashing**: Frozen structs are hashable:

```python
class Point(msgspec.Struct, frozen=True):
    x: float
    y: float

p1 = Point(x=1.0, y=2.0)
p2 = Point(x=1.0, y=2.0)

# Can be used in sets and as dict keys
points = {p1, p2}  # {Point(x=1.0, y=2.0)}

point_map = {p1: "origin area"}
print(point_map[p2])  # "origin area" - same hash
```

## Union Types (Tagged Unions)

Tagged unions allow discriminating between multiple struct types:

```python
from typing import ClassVar, Literal
import msgspec

class Dog(msgspec.Struct, tag="dog"):
    type: ClassVar[Literal["dog"]] = "dog"
    name: str
    breed: str

class Cat(msgspec.Struct, tag="cat"):
    type: ClassVar[Literal["cat"]] = "cat"
    name: str
    lives: int

type Animal = Dog | Cat

# Serialization includes tag
dog = Dog(name="Rex", breed="Labrador")
encoded = msgspec.json.encode(dog)
# {"type":"dog","name":"Rex","breed":"Labrador"}

# Deserialization uses tag to determine type
decoder = msgspec.json.Decoder(type=Animal)
animal = decoder.decode(b'{"type":"cat","name":"Whiskers","lives":9}')
print(type(animal).__name__)  # "Cat"
print(animal.lives)  # 9
```

**Custom tag field**:

```python
class Success(msgspec.Struct, tag_field="status", tag="ok"):
    status: ClassVar[Literal["ok"]] = "ok"
    data: dict

class Error(msgspec.Struct, tag_field="status", tag="error"):
    status: ClassVar[Literal["error"]] = "error"
    message: str

type Response = Success | Error

# Tag field is "status" instead of "type"
error = Error(message="Not found")
encoded = msgspec.json.encode(error)
# {"status":"error","message":"Not found"}
```

## Nested Structs

Structs can contain other structs:

```python
class Address(msgspec.Struct):
    street: str
    city: str
    zip_code: str

class Person(msgspec.Struct):
    name: str
    age: int
    address: Address  # Nested struct

person = Person(
    name="Alice",
    age=30,
    address=Address(
        street="123 Main St",
        city="Boston",
        zip_code="02101"
    )
)

# Nested serialization
encoded = msgspec.json.encode(person)
# {"name":"Alice","age":30,"address":{"street":"123 Main St","city":"Boston","zip_code":"02101"}}

# Nested deserialization
decoded = msgspec.json.decode(encoded, type=Person)
print(decoded.address.city)  # "Boston"
```

## Struct Options

### frozen=True (Immutable)

```python
class Point(msgspec.Struct, frozen=True):
    x: float
    y: float

point = Point(x=1.0, y=2.0)
# point.x = 3.0  # AttributeError: cannot set attribute

# Use replace() to create modified copies
new_point = msgspec.structs.replace(point, x=3.0)
print(new_point)  # Point(x=3.0, y=2.0)
```

**Benefits**:
- Thread-safe (immutable)
- Hashable (can be used in sets/dict keys)
- Prevents accidental modification
- Ideal for config objects, coordinates, constants

### kw_only=True (Keyword-Only Arguments)

```python
class Config(msgspec.Struct, kw_only=True):
    api_key: str
    timeout: int = 30
    max_retries: int = 3

# Must use keyword arguments
config = Config(api_key="secret-123")

# Positional arguments fail
# Config("secret-123")  # TypeError
```

**Benefits**:
- Explicit field names improve readability
- Allows fields with defaults before required fields
- Prevents argument order mistakes

### omit_defaults=True (Omit Default Values)

```python
class User(msgspec.Struct, omit_defaults=True):
    name: str
    role: str = "user"
    active: bool = True

user = User(name="Alice")
encoded = msgspec.json.encode(user)
# {"name":"Alice"}  - role and active omitted (they have default values)

user2 = User(name="Bob", role="admin")
encoded2 = msgspec.json.encode(user2)
# {"name":"Bob","role":"admin"}  - role included (not default value)
```

**Benefits**:
- Smaller payload size
- Cleaner JSON output
- Useful for partial updates

### forbid_unknown_fields=True (Strict Validation)

```python
class User(msgspec.Struct, forbid_unknown_fields=True):
    name: str
    age: int

# Valid JSON
data = b'{"name":"Alice","age":30}'
user = msgspec.json.decode(data, type=User)  # OK

# Invalid - extra field
data_extra = b'{"name":"Alice","age":30,"role":"admin"}'
# msgspec.json.decode(data_extra, type=User)  # ValidationError: unknown field 'role'
```

**Benefits**:
- Catches typos in field names
- Enforces strict schema compliance
- Prevents silent data loss

### Combining Options

```python
class ImmutableConfig(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """Strict, immutable configuration"""

    api_key: str
    base_url: str
    timeout: int = 30
    max_retries: int = 3

# Must use keywords, immutable, strict validation
config = ImmutableConfig(api_key="secret", base_url="https://api.example.com")
```

## Type Validation

msgspec performs automatic type validation during deserialization:

```python
class User(msgspec.Struct):
    name: str
    age: int

# Valid
user = msgspec.json.decode(b'{"name":"Alice","age":30}', type=User)

# Invalid - wrong type
try:
    msgspec.json.decode(b'{"name":"Alice","age":"thirty"}', type=User)
except msgspec.ValidationError as e:
    print(e)  # Expected `int`, got `str`
```

See [validation.md](validation.md) for detailed constraint validation.

## Best Practices

1. **Use `msgspec.Meta` for documentation and constraints**: Self-documenting, validated fields
2. **Always use `field(default_factory=...)` for mutable defaults**: Prevents shared state bugs
3. **Use `frozen=True` for immutable data**: Configs, coordinates, constants
4. **Use `kw_only=True` for flexibility**: Allows fields with defaults before required fields
5. **Use tagged unions for discriminated types**: Type-safe polymorphism
6. **Use `forbid_unknown_fields=True` for strict schemas**: Catch typos and enforce compliance
7. **Keep structs focused**: Single responsibility principle

## Reference Resources

- [msgspec Official Documentation - Structs](https://jcristharif.com/msgspec/structs.html)
- [best-practices.md](best-practices.md) - Comprehensive best practices guide
- [validation.md](validation.md) - Validation and constraints guide
