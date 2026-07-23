# msgspec Serialization Guide

This document provides detailed guidance on msgspec's serialization capabilities.

## Overview

[msgspec Serialization Documentation](https://jcristharif.com/msgspec/usage.html)

msgspec supports multiple serialization protocols:
- **JSON** - Human-readable, widely compatible
- **MessagePack** - Binary format, compact, fast
- **YAML** - Configuration files (requires `msgspec[yaml]`)
- **TOML** - Configuration files (requires `msgspec[toml]`)

## Basic Usage

### Simple Encoding and Decoding

```python
import msgspec

class User(msgspec.Struct):
    name: str
    age: int

# Encode
user = User(name="Alice", age=30)
encoded = msgspec.json.encode(user)
# b'{"name":"Alice","age":30}'

# Decode
decoded = msgspec.json.decode(encoded, type=User)
# User(name='Alice', age=30)
```

### Protocol Switching

All protocols use the same API - just change the module:

```python
# JSON
json_data = msgspec.json.encode(user)
user = msgspec.json.decode(json_data, type=User)

# MessagePack
msgpack_data = msgspec.msgpack.encode(user)
user = msgspec.msgpack.decode(msgpack_data, type=User)

# YAML (requires msgspec[yaml])
yaml_data = msgspec.yaml.encode(user)
user = msgspec.yaml.decode(yaml_data, type=User)

# TOML (requires msgspec[toml])
toml_data = msgspec.toml.encode(user)
user = msgspec.toml.decode(toml_data, type=User)
```

## Encoders and Decoders

### Creating Encoders and Decoders

For better performance, create reusable encoder/decoder instances:

```python
# Create encoder
encoder = msgspec.json.Encoder()

# Create typed decoder
decoder = msgspec.json.Decoder(type=User)

# Use them
encoded = encoder.encode(user)
decoded = decoder.decode(encoded)
```

### Reusing Encoders/Decoders

**✓ Efficient** (reuse instances):

```python
encoder = msgspec.json.Encoder()
decoder = msgspec.json.Decoder(type=User)

for item in large_dataset:
    encoded = encoder.encode(item)
    decoded = decoder.decode(encoded)
```

**✗ Inefficient** (create new instances each time):

```python
for item in large_dataset:
    encoded = msgspec.json.encode(item)  # Creates new encoder each time
    decoded = msgspec.json.decode(encoded, type=User)  # Creates new decoder
```

### JSONL Format

For JSON Lines (newline-delimited JSON):

```python
encoder = msgspec.json.Encoder()

users = [
    User(name="Alice", age=30),
    User(name="Bob", age=25),
]

# Encode as JSONL
jsonl_bytes = encoder.encode_lines(users)
# b'{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'

# Write to file
with open("users.jsonl", "wb") as f:
    f.write(jsonl_bytes)

# Read from file
decoder = msgspec.json.Decoder(type=User)
with open("users.jsonl", "rb") as f:
    for line in f:
        user = decoder.decode(line.strip())
        print(user)
```

### Encoding/Decoding Options

**Encoder Options**:

```python
encoder = msgspec.json.Encoder(
    enc_hook=custom_encoder,  # Custom type encoding hook
    order="sorted",           # Sort dict keys: None (default) | "sorted" | "deterministic"
)
```

**Decoder Options**:

```python
decoder = msgspec.json.Decoder(
    type=User,                # Expected type
    dec_hook=custom_decoder,  # Custom type decoding hook
    strict=True,              # Strict validation (default: True)
)
```

## Custom Type Handling

### Using enc_hook and dec_hook

For types not natively supported (like `pathlib.Path`):

```python
from pathlib import Path

def enc_hook(obj):
    """Custom encoding hook"""
    if isinstance(obj, Path):
        return str(obj)
    raise NotImplementedError(f"Unsupported type: {type(obj)}")

def dec_hook(type_, obj):
    """Custom decoding hook"""
    if type_ is Path:
        return Path(obj)
    raise NotImplementedError(f"Unsupported type: {type_}")

class Project(msgspec.Struct):
    name: str
    path: Path

encoder = msgspec.json.Encoder(enc_hook=enc_hook)
decoder = msgspec.json.Decoder(type=Project, dec_hook=dec_hook)

project = Project(name="MyApp", path=Path("/home/user/myapp"))
encoded = encoder.encode(project)
decoded = decoder.decode(encoded)
```

**Important**: Hooks are ONLY called for non-native types. msgspec natively supports datetime, Enum, UUID, Decimal, etc., so hooks are not needed for these types.

See [Converters Guide](converters.md) for detailed hook usage.

## Streaming

### Streaming Decode

For processing large JSON arrays without loading everything into memory:

```python
import msgspec

decoder = msgspec.json.Decoder(type=User)

with open("large_file.json", "rb") as f:
    # Assuming file contains: [{"name":"Alice","age":30}, {"name":"Bob","age":25}, ...]
    # This would need manual parsing or use of streaming JSON parser
    for line in f:
        if line.strip():
            user = decoder.decode(line)
            process(user)
```

For true streaming of JSON arrays, consider using JSONL format instead.

## Protocol-Specific Features

### JSON

- **Human-readable** - Easy to debug
- **Wide compatibility** - Supported everywhere
- **Text-based** - Larger than binary formats

```python
msgspec.json.encode(data)
```

### MessagePack

- **Binary format** - More compact than JSON
- **Faster** - Less parsing overhead
- **Extension types** - Support for custom binary types

```python
msgspec.msgpack.encode(data)
```

### YAML

- **Configuration files** - Human-editable
- **Comments** - Supports comments
- **Requires extra dependency** - Install with `msgspec[yaml]`

```python
msgspec.yaml.encode(data)  # Requires PyYAML
```

### TOML

- **Configuration files** - Python-friendly syntax
- **Type-safe** - Stricter than YAML
- **Requires extra dependency** - Install with `msgspec[toml]`

```python
msgspec.toml.encode(data)  # Requires tomli/tomli-w
```

## Best Practices

1. **Reuse encoder/decoder instances** for better performance
2. **Use appropriate protocol** for your use case:
   - APIs → JSON or MessagePack
   - Config files → YAML or TOML
   - Logs → JSONL
3. **Use typed decoders** (`Decoder(type=User)`) for automatic validation
4. **Use JSONL for large datasets** instead of JSON arrays
5. **Only write hooks for non-native types** (Path, ORM objects, etc.)

## Reference Resources

- [msgspec Official Documentation](https://jcristharif.com/msgspec/)
- [msgspec Usage Guide](https://jcristharif.com/msgspec/usage.html)
- [Supported Types](supported-types.md)
- [Converters Guide](converters.md)
