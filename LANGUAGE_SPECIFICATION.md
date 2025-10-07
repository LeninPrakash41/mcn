# MCN Language Specification v2.0

## Overview
MCN (Macincode) is a modern scripting language designed for AI-powered business automation, combining simplicity with powerful integration capabilities.

## File Extension
- **Primary**: `.mcn`
- **MIME Type**: `text/x-mcn`
- **Shebang**: `#!/usr/bin/env mcn`

## Language Features

### Core Syntax
```mcn
// Variables
var name = "MCN"
var version = 2.0
var isActive = true

// Functions
function greet(name) {
    return "Hello " + name
}

// Control Flow
if version >= 2.0
    log "MCN v2.0 or higher"
else
    log "Older version"

// Loops
var i = 0
while i < 5
    log "Count: " + i
    i = i + 1
```

### AI Integration
```mcn
use "ai"

var response = ai("Analyze this data", "gpt-4")
var sentiment = analyze_sentiment("MCN is amazing!")
```

### Database Operations
```mcn
use "db"

var users = query("SELECT * FROM users")
var result = batch_insert("logs", [{"event": "login"}])
```

### HTTP/API Integration
```mcn
use "http"

var data = get_json("https://api.example.com/data")
var response = post_form("https://api.example.com/submit", {"key": "value"})
```

## Standard Library Modules

### Core Modules
- `ai` - AI/ML operations
- `db` - Database connectivity
- `http` - HTTP/REST operations
- `file` - File system operations
- `crypto` - Cryptographic functions
- `time` - Date/time utilities

### Package Management
```mcn
import "package-name" as pkg
use "local-module"
```

## Language Standards

### Naming Conventions
- Variables: `snake_case`
- Functions: `snake_case`
- Constants: `UPPER_CASE`
- Modules: `kebab-case`

### Code Style
- Indentation: 4 spaces
- Line length: 88 characters
- Comments: `//` for single line, `/* */` for multi-line

## Compatibility
- **Minimum Python**: 3.8+
- **Platforms**: Windows, macOS, Linux
- **Architectures**: x86_64, ARM64

## Version History
- **v1.0**: Initial release
- **v2.0**: AI integration, enhanced syntax
- **v2.1**: Package system, type hints (planned)

## RFC Process
Language changes follow RFC (Request for Comments) process for community input.