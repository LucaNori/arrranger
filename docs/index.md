# Arrranger Documentation

Welcome to the Arrranger documentation. This index provides links to all available documentation resources.

## Overview

Arrranger is a robust tool for backing up and synchronizing media items between multiple Radarr and Sonarr instances. It provides automated backup and synchronization capabilities, ensuring that your media library data is preserved and can be easily restored or replicated across instances.

## Documentation Sections

### Core Documentation

- [Overview](overview.md) - High-level overview of Arrranger's architecture and components
- [Configuration Guide](configuration.md) - Detailed information about configuring Arrranger
- [Development Guide](development.md) - Instructions for setting up a development environment and contributing
- [Testing Guide](testing.md) - Information about the testing environment and writing tests

### Additional Resources

- [README](../README.md) - Project overview and quick start guide
- [CHANGELOG](../CHANGELOG.md) - History of changes and version updates

## Key Features

- **Database Backups**: Store media library data in a local SQLite database
- **Instance Synchronization**: Mirror media libraries between Radarr/Sonarr instances
- **Release History Tracking**: Optionally back up detailed release information
- **Scheduled Operations**: Automate backups and syncs using cron expressions
- **Filtering Options**: Selectively sync media based on quality profiles, folders, or tags

## Getting Started

1. Install Arrranger following the instructions in the [README](../README.md)
2. Configure your instances in the `arrranger_instances.json` file (see [Configuration Guide](configuration.md))
3. Run the application using the main entry point or the scheduler

## Architecture

Arrranger is designed with a modular architecture that separates concerns into distinct components:

- **Database Management**: Handles data storage and retrieval
- **API Communication**: Manages interactions with Radarr and Sonarr APIs
- **Configuration Management**: Handles loading and validating configuration
- **Media Server Management**: Coordinates operations between instances
- **Scheduling**: Provides automated execution of tasks
- **Logging**: Ensures consistent operation tracking

For more details, see the [Overview](overview.md) document.

## Usage Examples

### Backing Up a Radarr Instance

```json
"radarr-main": {
  "url": "http://radarr:7878",
  "api_key": "your-api-key-here",
  "type": "radarr",
  "backup": {
    "enabled": true,
    "schedule": {
      "type": "cron",
      "cron": "0 3 * * *"
    }
  }
}
```

### Syncing from a Parent to Child Instance

```json
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
```

For more configuration examples, see the [Configuration Guide](configuration.md).

## Contributing

Contributions to Arrranger are welcome! Please see the [Development Guide](development.md) for information on setting up a development environment and the recommended workflow for making changes to the codebase.

## Support

If you encounter any issues or have questions, please open an issue on the GitHub repository.