# Contributing to ZATCA Compliance Monitor

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/zatca-compliance-monitor.git
cd zatca-compliance-monitor
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
pip install -e .  # Install in editable mode
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Write docstrings for all public functions and classes
- Maximum line length: 100 characters

**Format code with Black:**
```bash
black zatca_monitor/
```

**Check with Flake8:**
```bash
flake8 zatca_monitor/ --max-line-length=100
```

## Testing

All new features must include tests.

**Run tests:**
```bash
pytest tests/ -v
```

**With coverage:**
```bash
pytest --cov=zatca_monitor tests/
```

## Commit Guidelines

- Use clear, descriptive commit messages
- Reference issue numbers when applicable
- Keep commits focused on a single change

**Format:**
```
[TYPE] Short description

Longer description if needed

Fixes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions/modifications
- `refactor`: Code refactoring
- `perf`: Performance improvements

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation if needed
6. Submit pull request

**PR Checklist:**
- [ ] Tests pass
- [ ] Code formatted with Black
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No merge conflicts

## Areas for Contribution

- **Validators**: Additional ZATCA compliance rules
- **Parsers**: Support for more invoice formats
- **Performance**: Optimization improvements
- **Documentation**: Examples, tutorials, translations
- **Testing**: Additional test cases and edge cases

## Questions?

Open an issue or reach out to the maintainers.

Thank you for contributing! 🎉
