# msgspec Validation and Constraints

This guide covers msgspec's validation capabilities using `msgspec.Meta` for declarative constraints.

## Overview

[msgspec Validation Documentation](https://jcristharif.com/msgspec/usage.html#schema-validation)

msgspec provides automatic validation during deserialization using `msgspec.Meta()`:

- **String constraints**: min_length, max_length, pattern
- **Numeric constraints**: gt, ge, lt, le, multiple_of
- **Collection constraints**: min_length, max_length
- **General metadata**: description, title, examples

**Benefits**:
- Validation happens automatically during decode
- Zero runtime overhead for valid data
- Clear, declarative constraints
- Self-documenting schemas
- Reduces boilerplate validation code

## Basic Usage

```python
from typing import Annotated
import msgspec

class User(msgspec.Struct):
    name: Annotated[str, msgspec.Meta(description="Username", min_length=1, max_length=100)]
    age: Annotated[int, msgspec.Meta(description="User age", ge=0, le=150)]
    email: Annotated[str, msgspec.Meta(description="Email address", pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")]

# Valid data
valid_json = b'{"name":"Alice","age":30,"email":"alice@example.com"}'
user = msgspec.json.decode(valid_json, type=User)
print(user)  # User(name='Alice', age=30, email='alice@example.com')

# Invalid - name too short
try:
    msgspec.json.decode(b'{"name":"","age":30,"email":"alice@example.com"}', type=User)
except msgspec.ValidationError as e:
    print(e)  # Expected `str` with length >= 1

# Invalid - age out of range
try:
    msgspec.json.decode(b'{"name":"Alice","age":200,"email":"alice@example.com"}', type=User)
except msgspec.ValidationError as e:
    print(e)  # Expected `int` with value <= 150

# Invalid - email pattern mismatch
try:
    msgspec.json.decode(b'{"name":"Alice","age":30,"email":"invalid"}', type=User)
except msgspec.ValidationError as e:
    print(e)  # Expected `str` matching pattern
```

## Supported Constraint Types

### String Constraints

```python
from typing import Annotated
import msgspec

class StringValidation(msgspec.Struct):
    # Length constraints
    username: Annotated[str, msgspec.Meta(min_length=3, max_length=20)]

    # Pattern matching (regex)
    email: Annotated[str, msgspec.Meta(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")]

    # Combined constraints
    phone: Annotated[str, msgspec.Meta(
        description="Phone number",
        pattern=r"^\+?1?\d{9,15}$",
        min_length=10,
        max_length=15
    )]

    # Exact length
    zip_code: Annotated[str, msgspec.Meta(min_length=5, max_length=5)]

# Examples
valid = StringValidation(
    username="alice",
    email="alice@example.com",
    phone="+12025551234",
    zip_code="02101"
)
```

**Common regex patterns**:
- Email: `r"^[\w\.-]+@[\w\.-]+\.\w+$"`
- URL: `r"^https?://[\w\.-]+\.\w+(/[\w\.-]*)*$"`
- UUID: `r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"`
- Phone: `r"^\+?1?\d{9,15}$"`
- ISO date: `r"^\d{4}-\d{2}-\d{2}$"`

### Numeric Constraints

```python
from typing import Annotated
import msgspec

class NumericValidation(msgspec.Struct):
    # Greater than
    positive_int: Annotated[int, msgspec.Meta(gt=0)]

    # Greater than or equal
    non_negative: Annotated[int, msgspec.Meta(ge=0)]

    # Less than
    below_hundred: Annotated[int, msgspec.Meta(lt=100)]

    # Less than or equal
    max_hundred: Annotated[int, msgspec.Meta(le=100)]

    # Range (inclusive)
    age: Annotated[int, msgspec.Meta(ge=0, le=150)]

    # Multiple of
    even_number: Annotated[int, msgspec.Meta(multiple_of=2)]
    percentage: Annotated[int, msgspec.Meta(ge=0, le=100, multiple_of=5)]

    # Float constraints
    price: Annotated[float, msgspec.Meta(gt=0.0, description="Price in USD")]
    discount: Annotated[float, msgspec.Meta(ge=0.0, le=1.0, description="Discount rate")]

# Examples
valid = NumericValidation(
    positive_int=42,
    non_negative=0,
    below_hundred=99,
    max_hundred=100,
    age=30,
    even_number=10,
    percentage=50,
    price=19.99,
    discount=0.15
)
```

### Collection Constraints

```python
from typing import Annotated
import msgspec

class CollectionValidation(msgspec.Struct):
    # List length
    tags: Annotated[list[str], msgspec.Meta(min_length=1, max_length=10)]

    # Non-empty list
    items: Annotated[list[int], msgspec.Meta(min_length=1)]

    # Fixed size
    coordinates: Annotated[list[float], msgspec.Meta(min_length=2, max_length=2)]

    # Dict constraints
    metadata: Annotated[dict[str, str], msgspec.Meta(description="Key-value metadata")]

# Examples
valid = CollectionValidation(
    tags=["python", "msgspec"],
    items=[1, 2, 3],
    coordinates=[40.7128, -74.0060],  # latitude, longitude
    metadata={"author": "Alice", "version": "1.0"}
)

# Invalid - empty list
try:
    CollectionValidation(tags=[], items=[1], coordinates=[0.0, 0.0], metadata={})
except msgspec.ValidationError as e:
    print(e)  # Expected `list` with length >= 1
```

### General Metadata

```python
from typing import Annotated
import msgspec

class DocumentedStruct(msgspec.Struct):
    """Well-documented struct with metadata"""

    user_id: Annotated[int, msgspec.Meta(
        description="Unique user identifier",
        title="User ID",
        examples=[1, 42, 1337]
    )]

    name: Annotated[str, msgspec.Meta(
        description="User's full name",
        title="Full Name",
        examples=["Alice Smith", "Bob Jones"]
    )]

    status: Annotated[str, msgspec.Meta(
        description="Account status",
        title="Status",
        examples=["active", "inactive", "suspended"]
    )]

# Metadata is used for:
# - Documentation generation
# - JSON Schema export
# - API specifications
# - Error messages
```

## Combining Constraints

Multiple constraints can be combined for powerful validation:

```python
from typing import Annotated
import msgspec

class Product(msgspec.Struct):
    """Product with comprehensive validation"""

    # String with length and pattern
    sku: Annotated[str, msgspec.Meta(
        description="Stock Keeping Unit",
        pattern=r"^[A-Z]{3}-\d{6}$",
        min_length=10,
        max_length=10
    )]

    # Numeric range with multiple_of
    price: Annotated[float, msgspec.Meta(
        description="Price in USD",
        gt=0.0,
        lt=1000000.0,
        multiple_of=0.01  # Cents precision
    )]

    # Integer range
    stock: Annotated[int, msgspec.Meta(
        description="Stock quantity",
        ge=0,
        le=10000
    )]

    # List with size and element constraints
    tags: Annotated[list[str], msgspec.Meta(
        description="Product tags",
        min_length=1,
        max_length=5
    )]

    # Nested validation
    dimensions: Annotated[dict[str, float], msgspec.Meta(
        description="Product dimensions (cm)"
    )]

# Example
product = Product(
    sku="ABC-123456",
    price=19.99,
    stock=100,
    tags=["electronics", "gadget"],
    dimensions={"width": 10.5, "height": 5.0, "depth": 2.5}
)
```

## Custom Validation

For complex validation logic beyond constraints, use `__post_init__`:

```python
import msgspec
from datetime import date

class DateRange(msgspec.Struct):
    """Date range with custom validation"""

    start_date: date
    end_date: date

    def __post_init__(self):
        """Validate start_date is before end_date"""
        if self.start_date >= self.end_date:
            raise ValueError(f"start_date must be before end_date: {self.start_date} >= {self.end_date}")

# Valid
range1 = DateRange(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))

# Invalid - start after end
try:
    range2 = DateRange(start_date=date(2024, 12, 31), end_date=date(2024, 1, 1))
except ValueError as e:
    print(e)  # start_date must be before end_date
```

**When to use `__post_init__`**:
- Cross-field validation
- Complex business rules
- Computed fields
- Database lookups
- External API validation

## Validation Error Handling

```python
from typing import Annotated
import msgspec

class User(msgspec.Struct):
    name: Annotated[str, msgspec.Meta(min_length=1, max_length=100)]
    age: Annotated[int, msgspec.Meta(ge=0, le=150)]
    email: Annotated[str, msgspec.Meta(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")]

# Catch specific validation errors
def safe_decode(data: bytes) -> User | None:
    """Safely decode with error handling"""
    try:
        return msgspec.json.decode(data, type=User)
    except msgspec.ValidationError as e:
        print(f"Validation failed: {e}")
        return None
    except msgspec.DecodeError as e:
        print(f"Decode failed: {e}")
        return None

# Examples
result1 = safe_decode(b'{"name":"Alice","age":30,"email":"alice@example.com"}')
# User(name='Alice', age=30, email='alice@example.com')

result2 = safe_decode(b'{"name":"","age":30,"email":"alice@example.com"}')
# Validation failed: Expected `str` with length >= 1

result3 = safe_decode(b'not json')
# Decode failed: ...
```

**Error information in ValidationError**:
- Field path (for nested structs)
- Expected type/constraint
- Actual value received
- Constraint details

## Validation Timing

msgspec validates data during:

1. **Deserialization** (decode):
   ```python
   # Validation happens here
   user = msgspec.json.decode(data, type=User)
   ```

2. **Type conversion** (msgspec.convert):
   ```python
   # Validation happens here
   user = msgspec.convert(data_dict, type=User)
   ```

**NOT during**:
- Struct initialization from Python code
- Field assignment (unless frozen=True)

```python
from typing import Annotated
import msgspec

class User(msgspec.Struct):
    age: Annotated[int, msgspec.Meta(ge=0, le=150)]

# Direct initialization - NO validation
user = User(age=200)  # OK - constraint not checked
print(user.age)  # 200

# Deserialization - validation happens
try:
    msgspec.json.decode(b'{"age":200}', type=User)
except msgspec.ValidationError as e:
    print(e)  # Expected `int` with value <= 150
```

**Workaround for initialization validation**:

```python
class User(msgspec.Struct):
    age: Annotated[int, msgspec.Meta(ge=0, le=150)]

    def __post_init__(self):
        """Validate constraints on initialization"""
        # Re-encode and decode to trigger validation
        encoded = msgspec.json.encode(self)
        msgspec.json.decode(encoded, type=User)

# Now validation happens on initialization
try:
    user = User(age=200)
except msgspec.ValidationError as e:
    print(e)  # Expected `int` with value <= 150
```

## Best Practices

1. **Use constraints instead of manual validation**: Declarative, automatic, zero overhead
2. **Provide descriptive metadata**: Helps with documentation and error messages
3. **Combine constraints thoughtfully**: Multiple constraints provide stronger guarantees
4. **Use `__post_init__` for complex validation**: Cross-field checks, business rules
5. **Handle ValidationError specifically**: Don't catch too broadly
6. **Test validation edge cases**: Boundary values, invalid patterns, type mismatches
7. **Document constraint rationale**: Why these limits? What do they protect against?

## Common Validation Patterns

### Email Validation

```python
from typing import Annotated
import msgspec

class Contact(msgspec.Struct):
    email: Annotated[str, msgspec.Meta(
        description="Email address",
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$"
    )]
```

### Percentage (0-100)

```python
from typing import Annotated
import msgspec

class Progress(msgspec.Struct):
    completion: Annotated[int, msgspec.Meta(
        description="Completion percentage",
        ge=0,
        le=100
    )]
```

### Positive Price

```python
from typing import Annotated
import msgspec

class Product(msgspec.Struct):
    price: Annotated[float, msgspec.Meta(
        description="Price in USD",
        gt=0.0,
        multiple_of=0.01  # Cents precision
    )]
```

### Non-Empty List

```python
from typing import Annotated
import msgspec

class Order(msgspec.Struct):
    items: Annotated[list[str], msgspec.Meta(
        description="Order items",
        min_length=1
    )]
```

### SKU/Code Pattern

```python
from typing import Annotated
import msgspec

class Product(msgspec.Struct):
    sku: Annotated[str, msgspec.Meta(
        description="Stock Keeping Unit",
        pattern=r"^[A-Z]{3}-\d{6}$"
    )]
```

### Phone Number

```python
from typing import Annotated
import msgspec

class Contact(msgspec.Struct):
    phone: Annotated[str, msgspec.Meta(
        description="Phone number",
        pattern=r"^\+?1?\d{9,15}$"
    )]
```

### Username

```python
from typing import Annotated
import msgspec

class User(msgspec.Struct):
    username: Annotated[str, msgspec.Meta(
        description="Username (alphanumeric + underscore)",
        pattern=r"^[a-zA-Z0-9_]+$",
        min_length=3,
        max_length=20
    )]
```

## Testing Validation

```python
import msgspec
import pytest
from typing import Annotated

class User(msgspec.Struct):
    name: Annotated[str, msgspec.Meta(min_length=1, max_length=100)]
    age: Annotated[int, msgspec.Meta(ge=0, le=150)]
    email: Annotated[str, msgspec.Meta(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")]

def test_valid_user():
    """Test valid user data"""
    data = b'{"name":"Alice","age":30,"email":"alice@example.com"}'
    user = msgspec.json.decode(data, type=User)
    assert user.name == "Alice"
    assert user.age == 30
    assert user.email == "alice@example.com"

def test_empty_name():
    """Test name length constraint"""
    data = b'{"name":"","age":30,"email":"alice@example.com"}'
    with pytest.raises(msgspec.ValidationError, match="length >= 1"):
        msgspec.json.decode(data, type=User)

def test_age_out_of_range():
    """Test age constraint"""
    data = b'{"name":"Alice","age":200,"email":"alice@example.com"}'
    with pytest.raises(msgspec.ValidationError, match="<= 150"):
        msgspec.json.decode(data, type=User)

def test_invalid_email():
    """Test email pattern constraint"""
    data = b'{"name":"Alice","age":30,"email":"invalid"}'
    with pytest.raises(msgspec.ValidationError, match="pattern"):
        msgspec.json.decode(data, type=User)
```

## Reference Resources

- [msgspec Official Documentation - Validation](https://jcristharif.com/msgspec/usage.html#schema-validation)
- [best-practices.md](best-practices.md) - Best practices guide
- [struct.md](struct.md) - Struct guide
