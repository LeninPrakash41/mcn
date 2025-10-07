# MSL (Macincode [aka] Micro Scripting Language) 

🚀 **The Future of AI-Powered Development** - A revolutionary scripting language that bridges the gap between natural language and code, designed for the AI era.

## 🌟 Vision

MSL empowers developers to build intelligent applications with unprecedented ease. By combining AI, databases, APIs, and frontend integration in a single, intuitive language, MSL transforms complex development workflows into simple, readable scripts.

## 🚀 Quick Start - No Installation Required!

### 1. Get MSL
```bash
git clone https://github.com/zeroappz/msl
cd msl
```

### 2. Run Your First Script
```bash
# Use the runner script (works immediately)
python run_msl.py run msl/examples/hello.msl

# Windows users can also use
msl.bat run msl/examples/hello.msl
```

### 3. Start Interactive REPL
```bash
python run_msl.py repl
```

### 4. Serve as API
```bash
python run_msl.py serve --file msl/examples/hello.msl --port 8080
```

### For Production Use
```bash
pip install -e .
# Then use directly: msl run script.msl
```

## ✨ Key Features

- 🤖 **Native AI Integration** - Built-in AI functions with multi-model support
- 🗄️ **Database Operations** - Universal connectivity with AI-assisted queries
- 🌐 **Full-Stack Ready** - Frontend integration and auto-generated APIs
- 🔧 **Developer Friendly** - Enhanced error logging and IDE support
- ⚡ **Zero Setup** - Run immediately without installation

## 📝 Basic Examples

### Hello World (hello.msl)
```msl
var name = "World"
var greeting = "Hello " + name + "!"
echo(greeting)
```

### Business Logic (business.msl)
```msl
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
python run_msl.py run hello.msl
python run_msl.py run business.msl
```

## 🎯 Advanced Features

### AI Integration
```msl
use "ai"

// AI-powered analysis
var response = ai("Analyze this data: " + data, "gpt-4")
echo(response)
```

### Database Operations
```msl
use "db"

// Simple database queries
var users = query("SELECT * FROM users")
echo(users)
```

### API Services
```msl
use "http"

// Create API endpoints
function get_user_data(user_id) {
    return query("SELECT * FROM users WHERE id = ?", (user_id))
}

export get_user_data
```

## 🛠️ Usage Modes

### Direct Script Execution
```bash
# Run any MSL script
python run_msl.py run script.msl

# Interactive development
python run_msl.py repl
```

### API Server Mode
```bash
# Serve single script as API
python run_msl.py serve --file script.msl --port 8080

# Serve directory of scripts
python run_msl.py serve --dir examples/ --port 8080
```

### Production Installation
```bash
pip install -e .
msl run script.msl
msl serve --file script.msl
```

## 📁 Project Structure

```
msl/
├── examples/           # Ready-to-run examples
│   ├── hello.msl      # Basic hello world
│   ├── business.msl   # Business logic demo
│   ├── ai_integration.msl
│   └── database_crud.msl
├── use-cases/         # Real-world scenarios
├── docs/             # Documentation
├── run_msl.py        # Main runner (no install needed)
└── msl.bat          # Windows batch file
```

## ✅ Key Benefits

- **No Installation Required**: Use `python run_msl.py` immediately
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

We're excited to have you join the MSL community! Whether you're fixing bugs, adding features, improving documentation, or sharing use cases, every contribution matters.

### How to Contribute

1. **Fork the repository** and create your feature branch
2. **Test your changes** using `python run_msl.py run examples/`
3. **Submit a pull request** with a clear description
4. **Join discussions** and help other developers

### Areas We Need Help

- 🐛 **Bug Reports & Fixes** - Help us improve stability
- 📝 **Documentation** - Make MSL more accessible
- 🎯 **Use Cases** - Share real-world applications
- 🔧 **Features** - Extend MSL's capabilities
- 🧪 **Testing** - Improve test coverage

### Get in Touch

- **Email**: [dev@mslang.org](mailto:dev@mslang.org)
- **GitHub Issues**: Report bugs and request features
- **Discussions**: Share ideas and get help

**Thank you for making MSL better for everyone!** 🚀

---

*MSL v2.0 - Bridging the gap between natural language and code***Blog**: Read about MSL development and use cases

## 🚀 What Makes MSL Special?

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

**Ready to build the future with MSL?** 🚀

```bash
# Quick backend script
python msl_cli.py examples/ai_integration.msl

# Or full-stack project
msl init my-ai-app --frontend react
cd my-ai-app
msl run msl/main.msl
```

*Join thousands of developers already building with MSL!*atural language meets programming
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

**Ready to build the future with MSL?** 🚀

```bash
msl init my-ai-app --frontend react
cd my-ai-app
msl run msl/main.msl
```

*Join thousands of developers already building with MSL!*