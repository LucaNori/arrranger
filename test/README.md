# Arrranger Tests

This directory contains automated tests for the Arrranger application. The tests are organized to cover unit tests for individual components as well as integration tests for interactions between components.

## Test Structure

- **Unit Tests**: Test individual components in isolation
  - `test_arrranger_logging.py`: Tests for the logging module
  - `test_arrranger_scheduler.py`: Tests for the scheduler module
  - `test_arrranger_sync.py`: Tests for the sync module

- **Integration Tests**: Test interactions between components
  - `test_integration.py`: Tests for end-to-end functionality

- **Test Configuration**:
  - `conftest.py`: Shared pytest fixtures
  - `pytest.ini`: Pytest configuration

## Running Tests

### Prerequisites

Ensure you have pytest installed:

```bash
pip install pytest pytest-cov
```

### Running All Tests

From the project root directory:

```bash
pytest
```

### Running Specific Test Files

```bash
# Run only logging tests
pytest test/test_arrranger_logging.py

# Run only scheduler tests
pytest test/test_arrranger_scheduler.py

# Run only sync tests
pytest test/test_arrranger_sync.py

# Run only integration tests
pytest test/test_integration.py
```

### Running Tests with Coverage

```bash
# Run tests with coverage report
pytest --cov=src --cov-report=term --cov-report=html
```

This will generate a coverage report in the terminal and an HTML report in the `htmlcov` directory.

## Test Coverage

The tests cover the following key areas:

1. **Logging Module**
   - Timestamp formatting
   - Count calculations
   - Backup and sync operation logging
   - Media count retrieval

2. **Scheduler Module**
   - Schedule management (cron expressions)
   - Backup operations
   - Sync operations
   - Task scheduling

3. **Sync Module**
   - Database operations
   - API client interactions
   - Configuration management
   - Media server management
   - Backup and sync operations

4. **Integration**
   - End-to-end backup operations
   - End-to-end sync operations
   - Scheduler integration

## Mocking Strategy

The tests use extensive mocking to isolate components and avoid external dependencies:

- Database connections are mocked to avoid actual database operations
- HTTP requests are mocked to avoid actual API calls
- File system operations are mocked to avoid actual file I/O
- Time-dependent functions are mocked for consistent test results

## Adding New Tests

When adding new tests:

1. Follow the existing naming conventions: `test_*.py` for files, `Test*` for classes, and `test_*` for functions
2. Use the shared fixtures from `conftest.py` where appropriate
3. Ensure tests are isolated and do not depend on external resources
4. Add appropriate docstrings to explain what each test is checking
5. Update this README if you add new test categories or significant functionality