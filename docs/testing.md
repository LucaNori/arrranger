# Arrranger Testing Guide

## Overview

Arrranger includes a comprehensive test suite to ensure functionality and prevent regressions. The testing approach combines unit tests for individual components and integration tests for end-to-end verification.

## Testing Environment

### Docker-Based Testing Environment

The `test/docker-compose.test.yml` file defines a testing environment with isolated Radarr and Sonarr instances:

```yaml
version: '3.8'

services:
  # Radarr service for movie management testing
  radarr:
    image: lscr.io/linuxserver/radarr:latest
    container_name: test-radarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
    volumes:
      - ./radarr/config:/config
      - ./media/movies:/movies
      - ./downloads:/downloads
    ports:
      - "7878:7878"
    restart: unless-stopped

  # Sonarr service for TV show management testing
  sonarr:
    image: lscr.io/linuxserver/sonarr:latest
    container_name: test-sonarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
    volumes:
      - ./sonarr/config:/config
      - ./media/tv:/tv
      - ./downloads:/downloads
    ports:
      - "8989:8989"
    restart: unless-stopped
```

### Starting the Test Environment

To start the testing environment:

```bash
cd test
docker compose -f docker-compose.test.yml up -d
```

This creates:
- A Radarr instance accessible at http://localhost:7878
- A Sonarr instance accessible at http://localhost:8989

### Configuring Test Instances

After starting the containers, you'll need to:

1. Access each instance through its web interface
2. Complete the initial setup
3. Create API keys for testing
4. Configure root folders and quality profiles

## Test Structure

### Unit Tests

Unit tests focus on testing individual components in isolation, using mocks for dependencies:

- `test_arrranger_sync.py`: Tests for database operations, API interactions, and media server management
- `test_arrranger_logging.py`: Tests for logging functionality
- `test_arrranger_scheduler.py`: Tests for scheduling functionality

### Integration Tests

Integration tests verify end-to-end functionality:

- `test_integration.py`: Tests for complete workflows involving multiple components

### Test Fixtures

The `conftest.py` file defines common test fixtures used across multiple test files:

- Mock database connections
- Mock API responses
- Test configuration data

## Running Tests

### Running All Tests

To run the entire test suite:

```bash
pytest
```

### Running Specific Tests

To run a specific test file:

```bash
pytest test/test_arrranger_sync.py
```

To run a specific test class:

```bash
pytest test/test_arrranger_sync.py::TestDatabaseManager
```

To run a specific test method:

```bash
pytest test/test_arrranger_sync.py::TestDatabaseManager::test_init_database
```

### Test Coverage

To generate a test coverage report:

```bash
pytest --cov=src
```

For a detailed HTML coverage report:

```bash
pytest --cov=src --cov-report=html
```

This generates a report in the `htmlcov` directory, which you can view in a web browser.

## Writing Tests

### Test Structure

Each test file follows a similar structure:

1. Import necessary modules and classes
2. Define test classes for each component being tested
3. Implement setup and teardown methods
4. Write test methods for specific functionality

### Mocking

Tests use the `unittest.mock` module to mock dependencies:

```python
from unittest.mock import patch, MagicMock

# Mock a function or method
with patch('module.function') as mock_function:
    mock_function.return_value = expected_result
    # Test code that calls the function

# Mock a class
with patch('module.Class') as MockClass:
    mock_instance = MagicMock()
    MockClass.return_value = mock_instance
    # Test code that instantiates the class
```

### Assertions

Tests use the standard `unittest` assertions:

```python
# Assert equality
self.assertEqual(actual, expected)

# Assert truth
self.assertTrue(condition)

# Assert that a function was called
mock_function.assert_called_once_with(arg1, arg2)

# Assert that a function was called with specific arguments
mock_function.assert_called_with(arg1, arg2)
```

## Continuous Integration

Tests are automatically run in CI environments on pull requests and commits to the main branch. The CI pipeline:

1. Sets up the Python environment
2. Installs dependencies
3. Runs linting checks with Ruff
4. Runs the test suite with pytest
5. Generates and reports test coverage

## Troubleshooting Tests

### Common Issues

1. **Database Connection Errors**:
   - Ensure that database mocks are properly configured
   - Check that connections are properly closed in teardown

2. **API Mocking Issues**:
   - Verify that the correct API endpoints are being mocked
   - Ensure that mock responses match the expected format

3. **Docker Environment Issues**:
   - Check that the Docker containers are running
   - Verify that the ports are correctly mapped
   - Ensure that the API keys are correctly configured

### Debugging Tests

To run tests with more detailed output:

```bash
pytest -v
```

To enable print statements during tests:

```bash
pytest -v --capture=no
```

To debug a specific test:

```bash
pytest --pdb test/test_file.py::TestClass::test_method
```

This will drop into a debugger when an exception occurs.