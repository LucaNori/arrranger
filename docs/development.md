# Arrranger Development Guide

## Development Environment Setup

This guide provides instructions for setting up a development environment for Arrranger and outlines the recommended workflow for making changes to the codebase.

## Prerequisites

- Python 3.8 or higher
- Git
- Docker and Docker Compose (for testing)
- uv (recommended for dependency management)

## Setting Up the Development Environment

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/arrranger.git
cd arrranger
```

### 2. Install Dependencies

Using uv (recommended):

```bash
# Install uv if you don't have it
pip install uv

# Install development dependencies
uv pip install -e ".[dev]"
```

Using pip:

```bash
pip install -e ".[dev]"
```

This installs the package in development mode with all development dependencies.

## Project Structure

```
arrranger/
├── docs/             # Documentation files
├── src/              # Source code
│   ├── __init__.py
│   ├── arrranger_logging.py    # Logging functionality
│   ├── arrranger_scheduler.py  # Scheduling functionality
│   └── arrranger_sync.py       # Core sync and backup functionality
├── test/             # Test files
│   ├── __init__.py
│   ├── conftest.py
│   ├── docker-compose.test.yml # Test environment configuration
│   ├── test_arrranger_logging.py
│   ├── test_arrranger_scheduler.py
│   ├── test_arrranger_sync.py
│   └── test_integration.py
├── main.py           # Application entry point
├── pyproject.toml    # Project configuration and dependencies
├── README.md
└── uv.lock           # Dependency lock file
```

## Development Tools

### Code Quality Tools

Arrranger uses Ruff for linting and formatting:

#### Linting

```bash
# Run linting checks
ruff check .

# Apply auto-fixes
ruff check --fix .
```

#### Formatting

```bash
# Format code
ruff format .
```

### Testing

Arrranger uses pytest for testing:

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src

# Generate HTML coverage report
pytest --cov=src --cov-report=html
```

See [testing.md](testing.md) for more details on testing.

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

1. Implement your changes
2. Add tests for new functionality
3. Run linting and formatting:
   ```bash
   ruff check --fix .
   ruff format .
   ```
4. Run tests to ensure everything works:
   ```bash
   pytest
   ```

### 3. Commit Changes

```bash
git add .
git commit -m "Description of your changes"
```

Use meaningful commit messages that describe what changes were made and why.

### 4. Push Changes

```bash
git push origin feature/your-feature-name
```

### 5. Create a Pull Request

Create a pull request on GitHub with a clear description of:
- What changes were made
- Why the changes were needed
- How to test the changes
- Any potential issues or limitations

## Dependency Management

### Adding a New Dependency

1. Add the dependency to `pyproject.toml`:
   ```toml
   [project]
   dependencies = [
       # Existing dependencies...
       "new-dependency>=1.0.0",
   ]
   ```

2. Update the lock file:
   ```bash
   uv pip compile pyproject.toml -o uv.lock
   ```

3. Install the updated dependencies:
   ```bash
   uv pip install -e ".[dev]"
   ```

### Adding a Development Dependency

1. Add the dependency to `pyproject.toml`:
   ```toml
   [project.optional-dependencies]
   dev = [
       # Existing dev dependencies...
       "new-dev-dependency>=1.0.0",
   ]
   ```

2. Update the lock file and install as above.

## Documentation

### Code Documentation

- Use docstrings for all modules, classes, and functions
- Follow the docstring format shown in the existing code
- Explain the "why" rather than the "what" in comments
- Keep comments concise and focused on explaining complex logic

Example:

```python
def calculate_counts(media_count: int, prev_media_count: int) -> tuple:
    """
    Calculate added and removed counts between operations.
    
    Derives the number of added and removed items between operations
    when these values aren't explicitly tracked during the operation.
    
    Args:
        media_count: Current number of media items
        prev_media_count: Previous number of media items
        
    Returns:
        tuple: Calculated (added_count, removed_count)
    """
    added_count = max(0, media_count - prev_media_count)
    removed_count = max(0, prev_media_count - media_count)
    return added_count, removed_count
```

### Project Documentation

- Update the README.md when making significant changes
- Update or add documentation in the docs/ directory
- Use Markdown for all documentation files

## Versioning

Arrranger follows [Semantic Versioning](https://semver.org/):

- MAJOR version for incompatible API changes
- MINOR version for backward-compatible functionality additions
- PATCH version for backward-compatible bug fixes

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create a new tag:
   ```bash
   git tag -a v1.0.0 -m "Version 1.0.0"
   git push origin v1.0.0
   ```
4. Create a new release on GitHub

## Debugging Tips

### Running in Debug Mode

You can run the application with more verbose logging by setting the logging level:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Using a Debugger

You can use the built-in Python debugger or an IDE like VS Code to debug the application:

```python
import pdb
pdb.set_trace()  # This will start the debugger at this point
```

### Common Issues

1. **Database Connection Issues**:
   - Check that the database file exists and is writable
   - Ensure connections are properly closed after use

2. **API Connection Issues**:
   - Verify that the API URL is correct
   - Check that the API key is valid
   - Ensure the media server is running and accessible

3. **Scheduling Issues**:
   - Validate cron expressions
   - Check that the system time is correct
   - Ensure the scheduler is running with sufficient permissions

## Contributing Guidelines

1. Follow the code style and documentation guidelines
2. Write tests for new functionality
3. Ensure all tests pass before submitting a pull request
4. Update documentation as needed
5. Be respectful and constructive in code reviews

By following these guidelines, you'll help maintain a high-quality, well-documented codebase that's easy to understand and extend.