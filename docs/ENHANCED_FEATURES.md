# MCN v3.0 Enhanced Features

This document covers the new foundational features implemented in MCN v3.0, focusing on the enhanced module system, AI model management, and package registry.

## 🚀 Overview

MCN v3.0 introduces three foundational systems that differentiate it from other programming languages:

1. **Enhanced Module System** - Dynamic package loading with dependency resolution
2. **AI Model Management** - Multi-provider AI model registration and fine-tuning
3. **Package Registry** - Centralized package discovery and distribution

## 📦 Enhanced Module System

### Features

- **Dynamic Loading**: Packages are loaded on-demand when requested
- **Dependency Resolution**: Automatic installation of package dependencies
- **Version Management**: Support for specific package versions
- **Local Packages**: Create and use local packages for development

### Usage

```mcn
// Install packages
install("ai_v3")
install("iot", "3.0.0")  // Specific version

// Use packages
use "ai_v3"
use "iot"

// Search for packages
var packages = search("machine learning", "", 10)
for package in packages {
    log(package.name + ": " + package.description)
}

// List installed packages
var installed = list(true)  // true for installed only
```

### CLI Commands

```bash
# Install packages
mcn install ai_v3
mcn install iot --version 3.0.0

# Search packages
mcn search "machine learning"
mcn search --category ai --limit 5

# List packages
mcn list
mcn list --all

# Uninstall packages
mcn uninstall old_package
```

## 🤖 AI Model Management

### Features

- **Multi-Provider Support**: OpenAI, Anthropic, Google, Local (Ollama), HuggingFace
- **Model Registration**: Register custom models with configurations
- **Fine-Tuning**: Fine-tune models on custom datasets
- **Usage Tracking**: Monitor model usage and performance
- **Active Model**: Set default model for AI operations

### Supported Providers

| Provider | Models | Fine-Tuning | API Key Required |
|----------|--------|-------------|------------------|
| OpenAI | GPT-4, GPT-3.5-turbo | ✅ | Yes |
| Anthropic | Claude-3 variants | ❌ | Yes |
| Google | Gemini Pro | ✅ | Yes |
| Local | Llama2, CodeLlama | ✅ | No |
| HuggingFace | Various models | ❌ | Yes |

### Usage

```mcn
// Register models
register("my-gpt4", "openai", "gpt-4", {"temperature": 0.7})
register("local-llama", "local", "llama2:latest")

// Set active model
set_model("my-gpt4")

// Run AI models
var response = run("Explain quantum computing", "my-gpt4")
log("Response: " + response)

// Fine-tune models
train("gpt-3.5-turbo", "training_data.csv", "custom-model")
```

### CLI Commands

```bash
# List models
mcn models list
mcn models list --provider openai

# Register models
mcn models register my-model openai gpt-4
mcn models register local-llama local llama2:latest

# Set active model
mcn models set my-model

# Run models
mcn models run "Hello world" --model my-model

# Delete models
mcn models delete old-model
```

## 🏪 Package Registry

### Features

- **Package Discovery**: Search and browse available packages
- **Publishing**: Publish your own packages to the registry
- **Statistics**: View download counts and popularity
- **Categories**: Organize packages by functionality
- **Templates**: Generate package templates for development

### Built-in Packages

| Package | Description | Functions |
|---------|-------------|-----------|
| `ai_v3` | Advanced AI model management | register, set_model, run, train |
| `iot` | IoT device connectivity | register, read, command |
| `events` | Event-driven programming | on, trigger, emit |
| `agents` | Autonomous AI agents | create, activate, think |
| `natural` | Natural language programming | translate, execute |
| `pipeline` | AI-powered data pipelines | create, run, transform |
| `ui` | Frontend UI components | button, input, form, table |
| `db` | Database operations | connect, query, insert |
| `http` | HTTP client utilities | get, post, put, delete |
| `auth` | Authentication utilities | login, logout, register |

### Usage

```mcn
// Search packages
var ai_packages = search("ai", "", 10)
var iot_packages = search("", "iot", 5)

// Get package info
var info = info("ai_v3")
log("Package: " + info.name)
log("Description: " + info.description)
log("Functions: " + info.functions)
```

### CLI Commands

```bash
# Search packages
mcn search "machine learning"
mcn search --category ai

# Package information
mcn info ai_v3

# Registry statistics
mcn registry stats
mcn registry popular
mcn registry recent

# Package development
mcn create-package my-sensors "Custom sensor utilities" "Your Name"
mcn publish my-package.zip
```

## 🛠️ Package Development

### Creating a Package

1. **Generate Template**:
```bash
mcn create-package my-sensors "Custom sensor utilities" "Your Name"
```

2. **Package Structure**:
```
my-sensors/
├── package.json          # Package metadata
├── src/
│   └── main.mcn         # Main package code
├── tests/
│   └── test.mcn         # Package tests
├── docs/
└── README.md            # Documentation
```

3. **Package Metadata** (`package.json`):
```json
{
  "name": "my-sensors",
  "version": "1.0.0",
  "description": "Custom sensor utilities",
  "author": "Your Name",
  "license": "MIT",
  "keywords": ["sensors", "iot", "hardware"],
  "dependencies": ["iot"],
  "functions": ["read_temperature", "read_humidity"],
  "main": "src/main.mcn"
}
```

4. **Main Code** (`src/main.mcn`):
```mcn
// my-sensors package
use "iot"

function read_temperature(sensor_id) {
    var data = device("read", sensor_id)
    return data.temperature
}

function read_humidity(sensor_id) {
    var data = device("read", sensor_id)
    return data.humidity
}

log("Package 'my-sensors' loaded successfully")
```

5. **Publish Package**:
```bash
# Create package archive
zip -r my-sensors.zip my-sensors/

# Publish to registry
mcn publish my-sensors.zip
```

## 🔧 Integration Examples

### Complete IoT Application

```mcn
// Install required packages
install("ai_v3")
install("iot")
install("events")
install("agents")

// Use packages
use "ai_v3"
use "iot"
use "events"
use "agents"

// Setup AI model
register("home-ai", "openai", "gpt-4")
set_model("home-ai")

// Register IoT devices
device("register", "temp_sensor", {"type": "temperature_sensor"})
device("register", "smart_thermostat", {"type": "thermostat"})

// Create intelligent agent
agent("create", "home_manager", {
    "prompt": "You manage a smart home system",
    "model": "home-ai",
    "tools": ["device", "log"]
})
agent("activate", "home_manager")

// Event-driven automation
on("temperature_change", "handle_temperature")

function handle_temperature(data) {
    var decision = agent("think", "home_manager", {
        "input": "Temperature is " + data.temperature + "°C. Adjust thermostat?"
    })
    log("AI Decision: " + decision)
    
    if data.temperature > 25 {
        device("command", "smart_thermostat", {"temperature": 22})
    }
}

// Monitor temperature
var temp = device("read", "temp_sensor")
trigger("temperature_change", {"temperature": temp})
```

### AI-Powered Data Pipeline

```mcn
// Setup AI and pipeline packages
install("ai_v3")
install("pipeline")
use "ai_v3"
use "pipeline"

// Register specialized model
register("data-analyzer", "openai", "gpt-4", {"temperature": 0.3})

// Create processing pipeline
pipeline("create", "customer_feedback", [
    {"type": "clean", "params": {"remove_special_chars": true}},
    {"type": "ai_classify", "params": {"categories": ["positive", "negative", "neutral"]}},
    {"type": "ai_extract", "params": {"type": "entities"}},
    {"type": "transform", "params": {"format": "structured"}}
])

// Process feedback data
var feedback = "Great product! Love the new features. John Smith from NYC."
var result = pipeline("run", "customer_feedback", feedback)

log("Sentiment: " + result.classification)
log("Entities: " + result.entities)
```

## 🎯 Best Practices

### Package Management

1. **Use Specific Versions**: Pin package versions for production
2. **Minimal Dependencies**: Only install what you need
3. **Regular Updates**: Keep packages updated for security
4. **Local Development**: Use local packages for custom functionality

### AI Model Management

1. **Provider Selection**: Choose providers based on use case
2. **Model Optimization**: Fine-tune models for specific tasks
3. **Cost Management**: Monitor usage and costs
4. **Fallback Models**: Have backup models for reliability

### Package Development

1. **Clear Documentation**: Write comprehensive README files
2. **Semantic Versioning**: Follow semver for version numbers
3. **Testing**: Include comprehensive tests
4. **Dependencies**: Minimize and document dependencies

## 🚀 Next Steps

The enhanced features provide the foundation for:

1. **VS Code Extension** - IDE integration with IntelliSense
2. **Web IDE** - Browser-based development environment
3. **Cloud Runtime** - Scalable deployment platform
4. **Full-Stack Framework** - Complete application development

These foundational systems enable MCN to become the leading AI-first development platform for modern applications.

## 📚 Additional Resources

- [Package Registry](https://registry.mslang.org) - Browse available packages
- [AI Model Providers](docs/AI_PROVIDERS.md) - Provider-specific documentation
- [Package Development Guide](docs/PACKAGE_DEVELOPMENT.md) - Detailed development guide
- [Examples Repository](examples/) - Real-world usage examples