# MCN Package Registry

## Overview
The MCN Package Registry is the official repository for MCN packages, similar to npm for Node.js or PyPI for Python.

## Registry URL
- **Production**: `https://registry.mslang.org`
- **Staging**: `https://staging.registry.mslang.org`

## Package Structure

### Package Manifest (`mcn.json`)
```json
{
  "name": "awesome-package",
  "version": "1.0.0",
  "description": "An awesome MCN package",
  "main": "index.mcn",
  "author": "Developer Name <dev@mslang.org>",
  "license": "MIT",
  "keywords": ["ai", "automation", "business"],
  "dependencies": {
    "http-utils": "^2.1.0",
    "ai-helpers": "~1.5.0"
  },
  "mcn": {
    "version": ">=2.0.0"
  },
  "repository": {
    "type": "git",
    "url": "https://github.com/user/awesome-package"
  }
}
```

### Package Commands
```bash
# Install package
mcn install awesome-package

# Install specific version
mcn install awesome-package@1.0.0

# Install globally
mcn install -g awesome-package

# Publish package
mcn publish

# Search packages
mcn search "ai automation"
```

## Standard Packages

### Core Packages
- `@mcn/ai` - Official AI integration
- `@mcn/db` - Database connectors
- `@mcn/http` - HTTP utilities
- `@mcn/crypto` - Cryptographic functions
- `@mcn/test` - Testing framework

### Community Packages
- `express-mcn` - Web framework
- `mongoose-mcn` - MongoDB ODM
- `redis-mcn` - Redis client
- `aws-mcn` - AWS SDK
- `stripe-mcn` - Payment processing

## Package Categories

### Business Automation
- CRM integrations
- ERP connectors
- Workflow engines
- Report generators

### AI/ML
- Model inference
- Data preprocessing
- Natural language processing
- Computer vision

### Infrastructure
- Cloud deployment
- Container orchestration
- Monitoring tools
- Security scanners

## Quality Standards

### Package Requirements
- Comprehensive documentation
- Test coverage >80%
- Semantic versioning
- Security audit passed

### Verification Badges
- ✅ **Verified**: Official MCN team review
- 🛡️ **Secure**: Security audit passed
- 📊 **Popular**: >10k downloads/month
- 🏆 **Quality**: High code quality score

## Registry API

### Package Information
```
GET /package/{name}
GET /package/{name}/{version}
```

### Search
```
GET /search?q={query}&category={category}
```

### Statistics
```
GET /stats/downloads/{name}
GET /stats/popular
```
