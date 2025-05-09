# Arrranger

a simple and automatic configuration-based tool to back up or synchronize media items (not media files) between multiple Radarr and Sonarr instances

## features

### simple to backup

- utilizes only two primary files: the configuration file (for automations) and the SQLite database (for backups and synchronization)

### manual operations

- you retain full control of the script. scheduling is optional and you can run manual operations as needed. to access the interactive menu in the container, execute: `docker exec -it your_container_name python arrranger_sync.py`. This menu allows you to:
  1. add a new media server instance
  2. remove a media server instance
  3. perform manual backup
  4. perform manual sync
  5. restore from a backup
  6. view configured instances
  7. restore releases from history (Experimental)
  8. exit

### automatic operations

- all automations are defined in the configuration file (`arrranger_instances.json`). from this file, you can:
  - schedule backups for multiple instances using cron expressions
  - schedule synchronization from a parent instance to a child instance, mirroring the parent's media library items on the child instance


### Release History Backup & Restore (Experimental)

- **Backup Release Details:** Optionally back up detailed information about the specific release file downloaded for each media item (including release title, indexer, GUID/hash).
- **Restore Specific Releases:** Attempt to redownload the *exact* same releases based on the backed-up history if media files are lost. This requires the release to still be available on the indexer.

the primary goal of Arrranger is to allow for a set-and-forget configuration, ensuring that your media library data can be easily restored if any of your instances encounter problems

## upcoming features

### advanced filtering (experimental - i advise not to use this feature!)

- **quality profile filtering**:
  - synchronize or back up only media with specific quality profiles
  - example: only synchronize 1080p content, excluding 4K content
- **root folder filtering**:
  - filter media based on their storage location
  - example: only synchronize media from specific folders
- **tag-based filtering**:
  - use tags tags to easily manage which media is synchronized or backed up
  - example: only synchronize media tagged with "sync" or "backup"

### custom rules when adding media (synchronization-related features)

- specify the root folder in which synchronized media items will be added
- define the quality profile to be applied to new media items added via synchronization

### lidarr support

- future support for Lidarr instances

## configuration

the program uses a JSON configuration file (`arrranger_instances.json`) to store instance settings. by default, this file should be placed in the `config` directory. a comprehensive example configuration is available in [arrranger_instances.json.example](arrranger_instances.json.example)

### configuration options

#### instance settings

- `name`: a unique identifier for the instance
- `url`: the base URL of the radarr/sonarr instance
- `api_key`: the API key for authentication
- `type`: either "radarr" or "sonarr"

#### backup settings

- `enabled`: indicates whether automatic backups are enabled (boolean: `true` or `false`)
- `backup_release_history`: (optional, boolean: `true` or `false`, default: `false`) If `true`, backs up detailed information about downloaded releases (indexer, GUID, etc.) to enable the experimental 'Restore Releases from History' feature.

- `schedule`: (optional if backups are disabled)
  - `type`: "cron" (currently, only "cron" is supported)
  - `cron`: a quoted string representing a cron expression

#### sync settings (optional)

- `parent_instance`: the name of the parent instance to synchronize from
- `schedule`: same format as the backup schedule
  - `type`: "cron"
  - `cron`: cron expression

#### filters (optional, NOT TESTED YET!)

- `quality_profiles`: a list of quality profile IDs to include
- `root_folders`: list of root folder paths to include
- `tags`: list of tags to filter by

## installations

### directory Structure

- `config/` - contains configuration files
- `data/` - contains the SQLite database
- both directories must be readable and writable by the script or the docker container

### local deployment using python

1. clone the repository:

  ```bash
  git clone https://github.com/lucanori/arrranger.git
  cd arrranger
  ```

2. install dependencies:

  ```bash
  pip3 install -r requirements.txt
  ```

3. create your configuration directory and file:

  ```bash
  mkdir -p config
  cp arrranger_instances.json.example config/arrranger_instances.json
  ```

4. edit `config/arrranger_instances.json` with your instance details

5. run the interactive script:

  ```bash
  python3 arrranger_sync.py
  ```
    - this provides an interactive menu with the following options:
      1. add a new media server instance
      2. remove a media server instance
      3. perform manual backup
      4. perform manual sync
      5. restore from backup
      6. view configured instances
      7. exit

5. or run the scheduler

  ```bash
  python3 arrranger_scheduler.py
  ```
  - this runs the scheduler that handles:
    - automatic backups based on the configuration file
    - automatic synchronization for parent-child instance relationships

### local deployment using Docker

this application can be run locally in a docker container. you can find the local Docker Compose configuration in [docker-compose.local.yml](docker-compose.local.yml).

1. clone the repository:

  ```bash
  git clone https://github.com/lucanori/arrranger.git
  cd arrranger
  ```

2. building the image

  ```bash
  docker compose -f docker-compose.local.yml build --no-cache
  ```

3. running the container

  ```bash
  docker compose -f docker-compose.local.yml up -d
  ```

### official container deployment using Docker

this will use the configuration defined in [docker-compose.yml](docker-compose.yml)

just add the service to your stack, or copy the docker compose to your folder and run:

```bash
docker compose up -d
```

## contributing

as this is my first experience with a public repository, i'm still learning a great deal. please keep that in mind when you're contributing

1. fork the repository
2. create your feature branch
3. commit your changes
4. push to the branch
5. create a new pull request

## license

this project is licensed under the MIT license - see the [LICENSE](LICENSE) file for details
