# MCN Programming Language

🚀 **The Industry Standard for AI-Powered Business Automation** - A modern scripting language designed for the AI era, combining simplicity with powerful integration capabilities.

[![GitHub Stars](https://img.shields.io/github/stars/zeroappz/mcn?style=social)](https://github.com/zeroappz/mcn)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCN Version](https://img.shields.io/badge/MCN-v3.0-blue.svg)](https://github.com/zeroappz/mcn/releases)
[![Package Registry](https://img.shields.io/badge/Registry-registry.mslang.org-green.svg)](https://registry.mslang.org)
[![Discord](https://img.shields.io/discord/123456789?label=Discord&logo=discord)](https://discord.gg/mcn-lang)

## 🌟 Vision

MCN empowers developers to build intelligent applications with unprecedented ease. By combining AI, databases, APIs, and frontend integration in a single, intuitive language, MCN transforms complex development workflows into simple, readable scripts.

## 🚀 Quick Start - No Installation Required!

### 1. Get MCN
```bash
git clone https://github.com/zeroappz/mcn
cd mcn
```

### 2. Run Your First Script
```bash
# Use the runner script (works immediately)
python run_mcn.py run mcn/examples/hello.mcn

# Windows users can also use
mcn.bat run mcn/examples/hello.mcn
```

### 3. Start Interactive REPL
```bash
python run_mcn.py repl
```

### 4. Serve as API
```bash
python run_mcn.py serve --file mcn/examples/hello.mcn --port 8080
```

### For Production Use
```bash
pip install -e .
# Then use directly: mcn run script.mcn
```

## ✨ Key Features

- 🤖 **Advanced AI Integration** - Multi-model support, fine-tuning, and model management
- 🏠 **IoT & Edge Computing** - Connect and control IoT devices with real-time monitoring
- 🔄 **Event-Driven Programming** - Asynchronous workflows and automation
- 🤖 **Autonomous Agents** - Create intelligent agents with memory and tools
- 🔧 **AI-Powered Pipelines** - Intelligent data processing and transformation
- 🗣️ **Natural Language Programming** - Write code in plain English
- 🗄️ **Database Operations** - Universal connectivity with AI-assisted queries
- 🌐 **Full-Stack Ready** - Frontend integration and auto-generated APIs
- ⚡ **Zero Setup** - Run immediately without installation

## 📝 Basic Examples

### Hello World (hello.mcn)
```mcn
var name = "World"
var greeting = "Hello " + name + "!"
echo(greeting)
```

### Business Logic (business.mcn)
```mcn
var order_total = 100.00
var tax_rate = 0.08
var tax = order_total * tax_rate
var final_total = order_total + tax

echo("Order: $" + order_total)
echo("Tax: $" + tax)
echo("Total: $" + final_total)
```

### Run Examples
```bash
python run_mcn.py run hello.mcn
python run_mcn.py run business.mcn
```

## 🎯 Advanced Features

### AI Model Management (v3.0)
```mcn
use "ai_v3"

// Register and manage multiple AI models
register("my-gpt4", "openai", {"temperature": 0.7})
set_model("my-gpt4")

// Fine-tune models on your data
train("gpt-3.5-turbo", "sales_data.csv", "sales-predictor")

// Use different models for different tasks
var summary = run("my-gpt4", "Summarize quarterly report")
var prediction = run("sales-predictor", "Predict next quarter")
```

### IoT & Automation (v3.0)
```mcn
use "iot"
use "events"

// Connect IoT devices
device("register", "temp_sensor", {"type": "temperature_sensor"})
device("register", "smart_light", {"type": "smart_light"})

// Event-driven automation
on event "high_temperature" handle_cooling

function handle_cooling(data) {
    device("command", "smart_light", {"command": "dim"})
}

// Monitor and respond
var temp = device("read", "temp_sensor")
if temp > 25 {
    trigger("high_temperature", {"temperature": temp})
}
```

### Autonomous Agents (v3.0)
```mcn
use "agents"

// Create intelligent agents
agent("create", "data_analyst", {
    "prompt": "You are a data analysis expert",
    "model": "gpt-4",
    "tools": ["query", "ai", "log"]
})

agent("activate", "data_analyst")
var analysis = agent("think", "data_analyst", {
    "input": "Analyze Q4 sales data: Revenue $2.5M, up 15%"
})
```

### Natural Language Programming (v3.0)
```mcn
use "natural"

// Write code in plain English
var code1 = translate("create a variable name with value John")
// Result: var name = "John"

var code2 = translate("if age greater than 18 then print adult")
// Result: if age > 18 { echo("adult") }

// Execute natural language directly
translate("send welcome email to new users", true)
```

### AI-Powered Data Pipelines (v3.0)
```mcn
use "pipeline"

// Create intelligent data processing pipelines
pipeline("create", "feedback_processor", [
    {"type": "clean", "params": {"remove_special_chars": true}},
    {"type": "ai_classify", "params": {"categories": ["positive", "negative"]}},
    {"type": "ai_extract", "params": {"type": "entities"}}
])

// Process data through pipeline
var result = pipeline("run", "feedback_processor", "Great product! Love it!")
```

## 🛠️ Usage Modes

### Direct Script Execution
```bash
# Run any MCN script
python run_mcn.py run script.mcn

# Interactive development
python run_mcn.py repl
```

### API Server Mode
```bash
# Serve single script as API
python run_mcn.py serve --file script.mcn --port 8080

# Serve directory of scripts
python run_mcn.py serve --dir examples/ --port 8080
```

### Production Installation
```bash
pip install -e .
mcn run script.mcn
mcn serve --file script.mcn
```

## 📁 Project Structure

```
mcn/
├── examples/           # Ready-to-run examples
│   ├── hello.mcn      # Basic hello world
│   ├── business.mcn   # Business logic demo
│   ├── ai_integration.mcn
│   └── database_crud.mcn
├── use-cases/         # Real-world scenarios
├── docs/             # Documentation
├── run_mcn.py        # Main runner (no install needed)
└── mcn.bat          # Windows batch file
```

## ✅ Key Benefits

- **No Installation Required**: Use `python run_mcn.py` immediately
- **No Path Setup**: Runner script handles all imports automatically
- **Cross-Platform**: Works on Windows, Linux, macOS
- **Production Ready**: Install with pip for production use
- **Rich Examples**: Comprehensive examples in `/examples` directory
- **Enhanced Error Handling**: Clear error messages with suggestions

## 📚 Learning Resources

- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** - Complete development guide
- **[Use Cases](use-cases/)** - Real-world examples and scenarios
- **[Examples](examples/)** - Ready-to-run code samples
- **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture overview

## 🤝 Welcome Contributors!

We're excited to have you join the MCN community! Whether you're fixing bugs, adding features, improving documentation, or sharing use cases, every contribution matters.

### How to Contribute

1. **Fork the repository** and create your feature branch
2. **Test your changes** using `python run_mcn.py run examples/`
3. **Submit a pull request** with a clear description
4. **Join discussions** and help other developers

### Areas We Need Help

- 🐛 **Bug Reports & Fixes** - Help us improve stability
- 📝 **Documentation** - Make MCN more accessible
- 🎯 **Use Cases** - Share real-world applications
- 🔧 **Features** - Extend MCN's capabilities
- 🧪 **Testing** - Improve test coverage

### Get in Touch

- **Email**: [dev@mslang.org](mailto:dev@mslang.org)
- **GitHub Issues**: Report bugs and request features
- **Discussions**: Share ideas and get help

**Thank you for making MCN better for everyone!** 🚀

---

*MCN v2.0 - Bridging the gap between natural language and code***Blog**: Read about MCN development and use cases

## 🚀 What Makes MCN Special?

### For Developers
- **Rapid Prototyping**: Build AI-powered apps in minutes
- **Full-Stack**: Backend + Frontend in one language
- **AI-First**: Native AI integration, not an afterthought
- **Developer-Friendly**: Clear errors, great tooling

### For Businesses
- **Faster Time-to-Market**: Reduce development cycles
- **Lower Costs**: Less code, fewer bugs, faster delivery
- **AI-Ready**: Built for the AI-powered future
- **Scalable**: From prototype to production

### For the Future
- **AI-Native**: Designed for human-AI collaboration
- **Intuitive**: Natural language meets programming
- **Extensible**: Plugin system for custom functionality
- **Open Source**: Community-driven development

## 📈 Roadmap

- **v2.1**: Visual programming interface
- **v2.2**: Multi-language code generation
- **v2.3**: Advanced AI model fine-tuning
- **v3.0**: Natural language programming

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Ready to build the future with MCN?** 🚀

```bash
# Quick backend script
python mcn_cli.py examples/ai_integration.mcn

# Or full-stack project
mcn init my-ai-app --frontend react
cd my-ai-app
mcn run mcn/main.mcn
```

*Join thousands of developers already building with MCN!*atural language meets programming
- **Extensible**: Plugin system for custom functionality
- **Open Source**: Community-driven development

## 📈 Roadmap

- **v2.1**: Visual programming interface
- **v2.2**: Multi-language code generation
- **v2.3**: Advanced AI model fine-tuning
- **v3.0**: Natural language programming

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Ready to build the future with MCN?** 🚀

```bash
mcn init my-ai-app --frontend react
cd my-ai-app
mcn run mcn/main.mcn
```

*Join thousands of developers already building with MCN!*
