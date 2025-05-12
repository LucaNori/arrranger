# Arrranger Configuration Guide

## Introduction

Arrranger uses a JSON configuration file to define media server instances, backup schedules, synchronization relationships, and filtering rules. This document provides detailed information about the configuration options available.

## Configuration File

By default, Arrranger looks for a file named `arrranger_instances.json` in the current working directory. The file path can be customized using the `CONFIG_FILE` environment variable.

## Basic Structure

The configuration file contains a JSON object where each key is an instance name and each value is an instance configuration object:

```json
{
  "instance-name-1": {
    // Instance 1 configuration
  },
  "instance-name-2": {
    // Instance 2 configuration
  }
}
```

## Instance Configuration

Each instance configuration requires the following base properties:

| Property | Type | Description |
|----------|------|-------------|
| `url` | String | Base URL of the Radarr/Sonarr instance (e.g., `http://radarr:7878`) |
| `api_key` | String | API key for authentication |
| `type` | String | Type of instance (`radarr` or `sonarr`) |

### Example Basic Configuration

```json
"radarr-main": {
  "url": "http://radarr:7878",
  "api_key": "your-api-key-here",
  "type": "radarr"
}
```

## Backup Configuration

To enable automated backups, add a `backup` object to the instance configuration:

| Property | Type | Description |
|----------|------|-------------|
| `enabled` | Boolean | Whether automated backups are enabled |
| `backup_release_history` | Boolean | (Optional) Whether to back up detailed release history |
| `schedule` | Object | Schedule configuration |

### Schedule Configuration

| Property | Type | Description |
|----------|------|-------------|
| `type` | String | Schedule type (currently only `cron` is supported) |
| `cron` | String | Cron expression defining the schedule |

### Example Backup Configuration

```json
"radarr-main": {
  "url": "http://radarr:7878",
  "api_key": "your-api-key-here",
  "type": "radarr",
  "backup": {
    "enabled": true,
    "backup_release_history": true,
    "schedule": {
      "type": "cron",
      "cron": "0 3 * * *"  // Run daily at 3:00 AM
    }
  }
}
```

## Synchronization Configuration

To enable synchronization from a parent instance, add a `sync` object to the instance configuration:

| Property | Type | Description |
|----------|------|-------------|
| `parent_instance` | String | Name of the parent instance to sync from |
| `schedule` | Object | Schedule configuration (same format as backup schedule) |

### Example Sync Configuration

```json
"radarr-backup": {
  "url": "http://radarr-backup:7878",
  "api_key": "your-backup-api-key",
  "type": "radarr",
  "sync": {
    "parent_instance": "radarr-main",
    "schedule": {
      "type": "cron",
      "cron": "0 4 * * *"  // Run daily at 4:00 AM
    }
  }
}
```

## Filtering Options

To filter which media items are synchronized or backed up, add a `filters` object to the instance configuration:

| Property | Type | Description |
|----------|------|-------------|
| `quality_profiles` | Array | List of quality profile IDs to include |
| `root_folders` | Array | List of root folder paths to include |
| `tags` | Array | List of tags to filter by |
| `min_year` | Number | Minimum year for media items |

### Example Filters Configuration

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
  },
  "filters": {
    "quality_profiles": ["1", "2"],
    "root_folders": ["/movies/hd", "/movies/4k"],
    "tags": ["sync", "backup"],
    "min_year": 2010
  }
}
```

## Complete Example

Here's a complete example configuration with multiple instances and various configurations:

```json
{
  "radarr-main": {
    "url": "http://radarr:7878",
    "api_key": "your-api-key-here",
    "type": "radarr",
    "backup": {
      "enabled": true,
      "backup_release_history": true,
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
    },
    "filters": {
      "quality_profiles": ["1"],
      "min_year": 2010
    }
  },
  "sonarr-main": {
    "url": "http://sonarr:8989",
    "api_key": "your-sonarr-api-key",
    "type": "sonarr",
    "backup": {
      "enabled": true,
      "schedule": {
        "type": "cron",
        "cron": "0 2 * * *"
      }
    }
  },
  "sonarr-backup": {
    "url": "http://sonarr-backup:8989",
    "api_key": "your-sonarr-backup-api-key",
    "type": "sonarr",
    "sync": {
      "parent_instance": "sonarr-main",
      "schedule": {
        "type": "cron",
        "cron": "0 5 * * *"
      }
    }
  }
}
```

## Cron Expression Guide

Arrranger uses cron expressions to define schedules. Here are some common examples:

| Cron Expression | Description |
|-----------------|-------------|
| `0 3 * * *` | Run at 3:00 AM every day |
| `0 */6 * * *` | Run every 6 hours |
| `0 0 * * 0` | Run at midnight on Sundays |
| `0 0 1 * *` | Run at midnight on the first day of each month |
| `0 0 1,15 * *` | Run at midnight on the 1st and 15th of each month |

The cron expression format is:
```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of the month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of the week (0-6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

## Environment Variables

Arrranger supports the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_FILE` | Path to the configuration file | `arrranger_instances.json` |
| `DB_NAME` | Path to the SQLite database file | `arrranger.db` |

## Configuration Validation

When Arrranger loads the configuration file, it validates:

1. The JSON syntax
2. Required fields for each instance
3. Cron expressions for schedules
4. Parent instance references

If validation fails, appropriate error messages will be displayed, and the affected functionality may be disabled.