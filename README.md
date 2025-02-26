# Arrranger

A config based tool to backup or synchronize media library information between multiple Radarr and Sonarr instances with advanced filtering and scheduling capabilities.

## Features

### Manual Operations
- Manual backup of any Radarr or Sonarr instance
- Manual sync between compatible instances (Radarr to Radarr, Sonarr to Sonarr)
- Manual restore from database backup to any instance

### Automatic Operations
- Scheduled backups with flexible timing options:
  - Daily backups at specific times
  - Weekly backups
  - Monthly backups
  - Custom cron schedules
- Parent-child instance relationships:
  - Designate a parent instance for automatic syncing
  - Child instances automatically sync from their parent on schedule

### Advanced Filtering
- Quality Profile Filtering:
  - Sync or backup only media with specific quality profiles
  - Example: Only sync 1080p content, exclude 4K
- Download Folder Filtering:
  - Filter media based on their save location
  - Example: Only sync media from specific folders
- Tag-based Filtering:
  - Use tags to control which media gets synced or backed up
  - Example: Only sync media tagged with "sync" or "backup"

## Configuration

The program uses a JSON configuration file (`arrranger_instances.json`) to store instance settings. By default, this file should be placed in the `config` directory. You can find a comprehensive example configuration in [arrranger_instances.json.example](arrranger_instances.json.example).

### Configuration Options

#### Instance Settings
- `name`: Unique identifier for the instance (for compatibility with original format)
- `url`: Base URL of the Radarr/Sonarr API
- `api_key`: API key for authentication
- `type`: Either "radarr" or "sonarr"

#### Backup Settings
- `enabled`: Whether automatic backups are enabled
- `schedule`:
  - `type`: "daily", "weekly", "monthly", or "cron"
  - `time`: Time in HH:MM format (for daily/weekly/monthly)
  - `cron`: Cron expression (if type is "cron")

#### Sync Settings
- `parent_instance`: Name of the parent instance to sync from
- `schedule`: Same format as backup schedule

#### Filters
- `quality_profiles`: List of quality profile IDs to include
- `root_folders`: List of root folder paths to include
- `tags`: List of tags to filter by

## Usage

### Main Program (arrranger_sync.py)

```bash
python arrranger_sync.py
```

This provides an interactive menu with the following options:
1. Add a new media server instance
2. Remove a media server instance
3. Perform manual backup
4. Perform manual sync
5. Restore from backup
6. View configured instances
7. Exit

### Scheduler (arrranger_scheduler.py)

```bash
python arrranger_scheduler.py
```

This runs the scheduler that handles:
- Automatic backups based on configured schedules with precise timing
- Automatic syncs for parent-child relationships
- Applies configured filters during operations
- Ensures tasks run exactly at their scheduled times, including cron schedules

## Dependencies
- `requests`: For API communication
- `sqlite3`: For local database storage
- `schedule`: For task scheduling
- `croniter`: For cron expression support

## Installation

### Standard Installation

1. Clone the repository:
```bash
git clone https://github.com/lucanori/arrranger.git
cd arrranger
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create your configuration directory and file:
```bash
mkdir -p config
cp arrranger_instances.json.example config/arrranger_instances.json
```

4. Edit `config/arrranger_instances.json` with your instance details

### Directory Structure

- `config/` - Contains configuration files
- `data/` - Contains the SQLite database and other persistent data
- Both directories must be readable/writable by the application or Docker container

## Docker Support

This application can be run in a Docker container. The complete Docker Compose configuration can be found in [docker-compose.yml](docker-compose.yml).

### Building the Image

```bash
docker build -t arrranger .
```

### Running the Container

```bash
docker run -d --name arrranger \
    -v /path/to/config:/config \
    -v /path/to/data:/data \
    -e CONFIG_FILE=/config/arrranger_instances.json \
    -e DB_NAME=/data/arrranger.db \
    arrranger
```

### Docker Compose

To run using Docker Compose, simply use:

```bash
docker-compose up -d
```

This will use the configuration defined in [docker-compose.yml](docker-compose.yml).

### Local Development with Docker

For local development, you can use the included docker-compose.local.yml file:

```bash
# Ensure data directory exists with proper permissions
mkdir -p data
touch data/arrranger.db
chmod 777 data data/arrranger.db

# Start the container
docker compose -f docker-compose.local.yml up -d
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
