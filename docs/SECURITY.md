# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| 1.x.x   | :x:                |

## Reporting Vulnerabilities

**Do not report security vulnerabilities through public GitHub issues.**

Email: **security@mslang.org**

Include:
- Type of issue
- Source file paths
- Step-by-step reproduction
- Impact assessment

## Security Best Practices

### Input Validation
```mcn
function validate_input(data) {
    if (typeof(data) != "string") {
        throw("Invalid input type")
    }
    return data
}
```

### Environment Variables
```mcn
use "env"
var api_key = env("API_KEY")  // Never hardcode secrets
```

### Database Security
```mcn
var user = query("SELECT * FROM users WHERE id = ?", (user_id))
```

## Response Timeline

- **24 hours**: Acknowledge receipt
- **72 hours**: Initial investigation
- **7 days**: Response action

## Security Features

- Sandboxed execution
- Input sanitization
- Secure defaults
- Audit logging

Thank you for keeping MCN secure! 🔒
