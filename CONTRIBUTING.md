# Contributing to MCN

## 🚀 Quick Start

1. Fork the repository
2. Clone: `git clone https://github.com/YOUR_USERNAME/mcn.git`
3. Create branch: `git checkout -b feature/your-feature`
4. Test: `python run_mcn.py run examples/hello.mcn`
5. Submit pull request

## 📋 Guidelines

### Code Contributions
- Core language changes require discussion in issues first
- Add tests for new functionality
- Follow existing code patterns
- Update documentation

### Testing
```bash
python run_mcn.py run examples/hello.mcn
python -m pytest test/
```

### Security
- Never commit API keys or secrets
- Report vulnerabilities to security@mslang.org
- Use environment variables for configuration

## 🛡️ Core Protection

MCN core interpreter and language specification are protected:
- Breaking changes require RFC process
- Core changes need maintainer approval
- MCN trademark cannot be used in derivatives

## 📝 Pull Request Process

1. Describe changes clearly
2. Link related issues
3. Add tests if needed
4. Ensure CI passes

## 🐛 Bug Reports

Include:
- MCN version
- Operating system
- Minimal reproduction example
- Expected vs actual behavior

## 💡 Feature Requests

- Check existing issues first
- Describe use case clearly
- Consider plugin vs core feature

Thank you for contributing! 🚀
