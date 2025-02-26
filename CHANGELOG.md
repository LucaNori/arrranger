# Changelog

All notable changes to the Arrranger project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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