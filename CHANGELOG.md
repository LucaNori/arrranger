# Changelog

All notable changes to the Arrranger project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2025-02-27

### Added
- New dedicated logging system via `arrranger_logging.py`
- Enhanced error handling during API operations
- Automatic quality profile and root folder detection when syncing
- Improved Docker container setup with proper timezone handling
- PUID/PGID support in Docker for better permission management
- Better validation and error reporting during sync operations

### Changed
- Simplified scheduler configuration to use cron expressions exclusively
- Improved sync process to handle both adding and removing shows properly
- Enhanced user experience in CLI selection menus
- Updated Docker startup process for more reliability
- Streamlined error messaging with more detailed information

### Fixed
- Instance selection logic in CLI menu
- Show syncing with proper TVDB ID handling
- Error handling during failed API requests
- Docker container permissions and file access

## [1.0.0] - 2025-02-26

### Added
- Initial release of Arrranger
- Manual operations
  - Backup capability for Radarr and Sonarr instances
  - Sync between compatible instances (Radarr to Radarr, Sonarr to Sonarr)
  - Restore functionality from database backups
- Automatic operations
  - Scheduled backups with flexible timing options:
    - Daily backups at specific times
    - Weekly backups
    - Monthly backups
    - Custom cron schedules with precise timing execution
  - Parent-child instance relationships:
    - Parent instance designation for automatic syncing
    - Child instances automatic sync from parent on schedule
- Advanced filtering capabilities
  - Quality profile filtering
  - Download folder filtering
  - Tag-based filtering
- Interactive menu system for manual operations
- Scheduler for automatic backup and sync operations with precise timing
- Comprehensive configuration system via JSON
- Docker support
  - Dockerfile for containerized deployment
  - Docker Compose configuration
- Documentation
  - User guide in README.md
  - Developer guide in DEVELOPER_GUIDE.md

### Changed
- None (initial release)

### Fixed
- None (initial release)