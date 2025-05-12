# Arrranger Overview

## Introduction

Arrranger is a specialized utility designed to manage, back up, and synchronize media libraries across multiple Radarr and Sonarr instances. It addresses the need for reliable data preservation and consistent configuration across media server deployments.

## Core Components

The application is structured with a modular design, separating concerns into distinct components:

### 1. Database Management

The `DatabaseManager` class handles all database operations, providing:
- Schema initialization and maintenance
- Media data storage and retrieval
- Release history tracking
- Differential backup capabilities

The SQLite database serves as the central storage mechanism, maintaining:
- Instance configurations
- Movie and show metadata
- Release history information

### 2. API Communication

The `ApiClient` class provides standardized communication with Radarr and Sonarr APIs:
- Connection verification
- Media data retrieval
- Error handling and reporting
- Timeout management

### 3. Configuration Management

The `ConfigManager` handles loading, saving, and validating configuration:
- JSON-based configuration file parsing
- Schedule validation (cron expressions)
- Instance configuration storage

### 4. Media Server Management

The `MediaServerManager` serves as the central coordinator:
- Instance registration and management
- Backup and sync operations
- Integration with other components

### 5. Scheduling

The `MediaServerScheduler` provides automated execution:
- Cron-based scheduling
- Task management and execution
- Periodic backups and syncs

### 6. Logging

The logging module ensures consistent operation tracking:
- Standardized log formats
- Operation success/failure reporting
- Differential counts for backups and syncs

## Data Flow

1. **Configuration Loading**:
   - Application reads instance configurations from JSON file
   - Validates connection details and schedules

2. **Backup Process**:
   - Retrieves media data from Radarr/Sonarr instances
   - Compares with existing database records
   - Stores new/updated items and removes deleted ones
   - Optionally backs up release history

3. **Sync Process**:
   - Compares source and destination instances
   - Determines items to add or remove
   - Applies filters based on configuration
   - Updates destination instance via API

4. **Scheduling**:
   - Evaluates when tasks should run based on cron expressions
   - Executes backups and syncs at scheduled times
   - Manages task lifecycle and rescheduling

## Architecture Benefits

The modular design of Arrranger provides several advantages:

1. **Separation of Concerns**: Each component has a specific responsibility
2. **Testability**: Components can be tested in isolation
3. **Maintainability**: Changes to one component have minimal impact on others
4. **Extensibility**: New features can be added with minimal changes to existing code

This architecture ensures that Arrranger remains robust, maintainable, and adaptable to future requirements.