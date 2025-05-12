# Arrranger

A robust tool for backing up and synchronizing media items between multiple Radarr and Sonarr instances.

## Overview

Arrranger is a configuration-based utility designed to simplify the management of multiple media server instances. It provides automated backup and synchronization capabilities for Radarr and Sonarr, ensuring that your media library data is preserved and can be easily restored or replicated across instances.

## Features

### Core Functionality

- **Database Backups**: Store media library data in a local SQLite database
- **Instance Synchronization**: Mirror media libraries between Radarr/Sonarr instances
- **Release History Tracking**: Optionally back up detailed release information
- **Scheduled Operations**: Automate backups and syncs using cron expressions
- **Filtering Options**: Selectively sync media based on quality profiles, folders, or tags

### Operation Modes

- **Interactive CLI**: Manage instances, perform manual operations, and view configurations
- **Scheduler**: Run automated backups and syncs based on configured schedules
- **Restoration**: Restore media libraries from backups or attempt to redownload specific releases

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

## Installation

### Prerequisites

- Python 3.8 or higher
- `uv` for dependency management (recommended)
- Docker (optional, for running tests or containerized deployment)

### Installing with uv

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/arrranger.git
   cd arrranger
   ```

2. Install dependencies using uv:
   ```bash
   uv pip install -e .
   ```

   For development dependencies:
   ```bash
   uv pip install -e ".[dev]"
   ```

### Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/arrranger.git
   cd arrranger
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

   For development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Usage

### Running the Application

To start the application using the main entry point:

```bash
python main.py
```

### Interactive CLI

For interactive management of media server instances:

```bash
python -m src.arrranger_sync
```

This provides a menu with the following options:
1. Add a new media server instance
2. Remove a media server instance
3. Perform manual backup
4. Perform manual sync
5. Restore from a backup
6. View configured instances
7. Restore releases from history
8. Exit

### Running the Scheduler

To start the scheduler for automated operations:

```bash
python -m src.arrranger_scheduler
```

## Configuration

The application uses a JSON configuration file (`arrranger_instances.json`) to store instance settings. By default, this file should be in the current working directory.

### Configuration Example

```json
{
  "radarr-main": {
    "url": "http://radarr:7878",
    "api_key": "your-api-key",
    "type": "radarr",
    "backup": {
      "enabled": true,
      "schedule": {
        "type": "cron",
        "cron": "0 3 * * *"
      }
    }
  },
  "radarr-backup": {
    "url": "http://radarr-backup:7878",
    "api_key": "your-backup-api-key",
    "type": "radarr",
    "sync": {
      "parent_instance": "radarr-main",
      "schedule": {
        "type": "cron",
        "cron": "0 4 * * *"
      }
    }
  }
}
```

See `arrranger_instances.json.example` for a more comprehensive example.

## Docker Deployment

### Local Development

A Docker Compose file is provided for local development:

```bash
docker compose -f docker-compose.local.yml build --no-cache
docker compose -f docker-compose.local.yml up -d
```

### Production Deployment

```bash
docker compose up -d
```

## Testing

### Running Tests

Tests can be run using pytest:

```bash
pytest
```

### Testing Environment

A Docker Compose file is provided for setting up a testing environment with Radarr and Sonarr instances:

```bash
cd test
docker compose -f docker-compose.test.yml up -d
```

This creates isolated Radarr and Sonarr instances for testing purposes.

## Code Quality

### Linting and Formatting

This project uses Ruff for linting and formatting:

```bash
# Run linter
ruff check .

# Apply auto-fixes
ruff check --fix .

# Format code
ruff format .
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the GNU General Public License Version 3 - see the [LICENSE](LICENSE) file for details.
