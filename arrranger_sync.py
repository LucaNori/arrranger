import sqlite3
import requests
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from croniter import croniter

# Use environment variables if available, otherwise use defaults
CONFIG_FILE = os.environ.get("CONFIG_FILE", "arrranger_instances.json")
DB_NAME = os.environ.get("DB_NAME", "arrranger.db")

class DatabaseManager:
    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name
        self.init_database()

    def init_database(self):
        """Initialize database tables with enhanced schema."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Movies table with enhanced fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                radarr_instance TEXT,
                title TEXT,
                year INTEGER,
                tmdb_id INTEGER,
                quality_profile TEXT,
                root_folder TEXT,
                tags TEXT,
                backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_movie UNIQUE (radarr_instance, tmdb_id)
            )
        """)

        # Shows table with enhanced fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sonarr_instance TEXT,
                title TEXT,
                year INTEGER,
                tvdb_id INTEGER,
                quality_profile TEXT,
                root_folder TEXT,
                tags TEXT,
                backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_show UNIQUE (sonarr_instance, tvdb_id)
            )
        """)

        conn.commit()
        conn.close()

    def save_media(self, instance_name: str, media_type: str, media_data: List[Dict[str, Any]]):
        """Save media data to database with enhanced metadata."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            if media_type == "movie":
                for item in media_data:
                    cursor.execute("""
                        INSERT OR REPLACE INTO movies
                        (radarr_instance, title, year, tmdb_id, quality_profile, root_folder, tags, backup_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        instance_name,
                        item.get("title"),
                        item.get("year"),
                        item.get("tmdbId"),
                        item.get("qualityProfileId"),
                        item.get("rootFolderPath"),
                        ','.join(str(tag) for tag in item.get("tags", []))
                    ))
            elif media_type == "show":
                for item in media_data:
                    cursor.execute("""
                        INSERT OR REPLACE INTO shows
                        (sonarr_instance, title, year, tvdb_id, quality_profile, root_folder, tags, backup_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        instance_name,
                        item.get("title"),
                        item.get("year"),
                        item.get("tvdbId"),
                        item.get("qualityProfileId"),
                        item.get("rootFolderPath"),
                        ','.join(str(tag) for tag in item.get("tags", []))
                    ))

            conn.commit()
            print(f"Media from {instance_name} ({media_type}s) saved to the database.")
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        finally:
            conn.close()

    def get_media(self, instance_name: str, media_type: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve media data from database with filter support."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            base_query = """
                SELECT title, year, {id_field}, quality_profile, root_folder, tags
                FROM {table}
                WHERE {instance_field} = ?
            """

            params = [instance_name]
            conditions = []

            if filters:
                if filters.get("quality_profiles"):
                    conditions.append("quality_profile IN (" + ",".join(["?" for _ in filters["quality_profiles"]]) + ")")
                    params.extend(filters["quality_profiles"])
                
                if filters.get("root_folders"):
                    conditions.append("root_folder IN (" + ",".join(["?" for _ in filters["root_folders"]]) + ")")
                    params.extend(filters["root_folders"])
                
                if filters.get("tags"):
                    tag_conditions = []
                    for tag in filters["tags"]:
                        tag_conditions.append("tags LIKE ?")
                        params.append(f"%{tag}%")
                    conditions.append("(" + " OR ".join(tag_conditions) + ")")

                if filters.get("min_year"):
                    conditions.append("year >= ?")
                    params.append(filters["min_year"])

            if conditions:
                base_query += " AND " + " AND ".join(conditions)

            if media_type == "movie":
                query = base_query.format(
                    id_field="tmdb_id",
                    table="movies",
                    instance_field="radarr_instance"
                )
            else:
                query = base_query.format(
                    id_field="tvdb_id",
                    table="shows",
                    instance_field="sonarr_instance"
                )

            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                media_item = {
                    "title": row[0],
                    "year": row[1],
                    "id": row[2],  # tmdb_id or tvdb_id
                    "quality_profile": row[3],
                    "root_folder": row[4],
                    "tags": row[5].split(',') if row[5] else []
                }
                result.append(media_item)

            return result
        finally:
            conn.close()

class MediaServerManager:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.instances = self.load_instances()

    def load_instances(self) -> Dict[str, Dict[str, Any]]:
        """Load media server instances from config file."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error loading config file: {e}")
                return {}
        return {}

    def save_instances(self):
        """Save media server instances to config file."""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.instances, f, indent=4)
            print("Media server instances configuration saved.")
        except IOError as e:
            print(f"Error saving config file: {e}")

    def validate_schedule(self, schedule: Dict[str, Any]) -> bool:
        """Validate schedule configuration."""
        if not isinstance(schedule, dict):
            return False

        valid_types = ["daily", "weekly", "monthly", "cron"]
        if schedule.get("type") not in valid_types:
            return False

        if schedule["type"] == "cron":
            if not schedule.get("cron") or not croniter.is_valid(schedule["cron"]):
                return False
        else:
            if not schedule.get("time") or not self._is_valid_time(schedule["time"]):
                return False

        return True

    def _is_valid_time(self, time_str: str) -> bool:
        """Validate time string format (HH:MM)."""
        try:
            datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False

    def add_instance(self, name: str, url: str, api_key: str, instance_type: str,
                    backup_config: Optional[Dict[str, Any]] = None,
                    sync_config: Optional[Dict[str, Any]] = None,
                    filters: Optional[Dict[str, Any]] = None) -> bool:
        """Add a new media server instance with enhanced configuration."""
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        # Validate backup configuration
        if backup_config and backup_config.get("enabled"):
            if not self.validate_schedule(backup_config.get("schedule", {})):
                print("Invalid backup schedule configuration")
                return False

        # Validate sync configuration
        if sync_config:
            if sync_config.get("parent_instance") and sync_config.get("parent_instance") not in self.instances:
                print(f"Parent instance {sync_config['parent_instance']} not found")
                return False
            if sync_config.get("schedule") and not self.validate_schedule(sync_config["schedule"]):
                print("Invalid sync schedule configuration")
                return False

        try:
            # Test connection and get instance metadata
            headers = {"X-Api-Key": api_key}
            
            # Test API connection
            response = requests.get(f"{url}/api/v3/system/status", headers=headers, timeout=30)
            response.raise_for_status()

            # Get quality profiles
            response_qp = requests.get(f"{url}/api/v3/qualityprofile", headers=headers, timeout=30)
            response_qp.raise_for_status()
            quality_profiles = response_qp.json()

            # Get root folders
            response_rf = requests.get(f"{url}/api/v3/rootfolder", headers=headers, timeout=30)
            response_rf.raise_for_status()
            root_folders = response_rf.json()

            # Get tags
            response_tags = requests.get(f"{url}/api/v3/tag", headers=headers, timeout=30)
            response_tags.raise_for_status()
            tags = response_tags.json()

            self.instances[name] = {
                "url": url,
                "api_key": api_key,
                "type": instance_type,
                "backup": backup_config or {"enabled": False},
                "sync": sync_config or {},
                "filters": filters or {},
                "metadata": {
                    "quality_profiles": quality_profiles,
                    "root_folders": root_folders,
                    "tags": tags
                }
            }
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to {name}: {e}")
            return False

    def manual_backup(self, instance_name: str) -> bool:
        """Perform manual backup of an instance."""
        instance = self.instances.get(instance_name)
        if not instance:
            print(f"Instance {instance_name} not found")
            return False

        try:
            media_data = self.fetch_media_data(instance_name, instance)
            if media_data:
                media_type = "movie" if instance["type"] == "radarr" else "show"
                self.db_manager.save_media(instance_name, media_type, media_data)
                print(f"Manual backup of {instance_name} completed successfully")
                return True
            return False
        except Exception as e:
            print(f"Error during manual backup of {instance_name}: {e}")
            return False

    def manual_sync(self, source_name: str, dest_name: str) -> bool:
        """Perform manual sync between instances."""
        source = self.instances.get(source_name)
        dest = self.instances.get(dest_name)

        if not source or not dest:
            print("Source or destination instance not found")
            return False

        if source["type"] != dest["type"]:
            print("Cannot sync between different types of instances")
            return False

        try:
            media_data = self.fetch_media_data(source_name, source)
            if not media_data:
                return False

            filters = dest.get("filters", {})
            if source["type"] == "radarr":
                return self.sync_movies_to_radarr(media_data, dest, filters)
            else:
                return self.sync_shows_to_sonarr(media_data, dest, filters)
        except Exception as e:
            print(f"Error during manual sync: {e}")
            return False

    def restore_from_backup(self, backup_instance_name: str, dest_name: str) -> bool:
        """Restore media from database backup to an instance."""
        dest = self.instances.get(dest_name)
        if not dest:
            print(f"Destination instance {dest_name} not found")
            return False

        try:
            media_type = "movie" if dest["type"] == "radarr" else "show"
            media_data = self.db_manager.get_media(backup_instance_name, media_type, dest.get("filters"))
            
            if not media_data:
                print(f"No media found in backup for {backup_instance_name}")
                return False

            if dest["type"] == "radarr":
                return self.sync_movies_to_radarr(media_data, dest, dest.get("filters", {}))
            else:
                return self.sync_shows_to_sonarr(media_data, dest, dest.get("filters", {}))
        except Exception as e:
            print(f"Error during restore from backup: {e}")
            return False

    def fetch_media_data(self, instance_name: str, instance_config: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Fetch media data from a server instance."""
        headers = {"X-Api-Key": instance_config["api_key"]}
        media_type = "movie" if instance_config["type"] == "radarr" else "series"
        
        try:
            response = requests.get(
                f"{instance_config['url']}/api/v3/{media_type}",
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from {instance_name}: {e}")
            return None

    def apply_filters(self, media_item: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Apply filters to a media item."""
        if not filters:
            return True

        if filters.get("quality_profiles") and str(media_item.get("qualityProfileId")) not in filters["quality_profiles"]:
            return False

        if filters.get("root_folders") and media_item.get("rootFolderPath") not in filters["root_folders"]:
            return False

        if filters.get("tags"):
            media_tags = set(media_item.get("tags", []))
            filter_tags = set(filters["tags"])
            if not media_tags.intersection(filter_tags):
                return False

        if filters.get("min_year") and media_item.get("year", 0) < filters["min_year"]:
            return False

        return True

    def sync_movies_to_radarr(self, movies: List[Dict[str, Any]], dest_config: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Sync movies to a Radarr instance with enhanced filtering."""
        headers = {
            "X-Api-Key": dest_config["api_key"],
            "Content-Type": "application/json"
        }

        success = True
        for movie in movies:
            if not self.apply_filters(movie, filters):
                continue

            try:
                data = {
                    "title": movie["title"],
                    "year": movie["year"],
                    "tmdbId": movie["id"],
                    "qualityProfileId": movie.get("quality_profile", 1),
                    "rootFolderPath": movie.get("root_folder", "/movies"),
                    "monitored": True,
                    "tags": movie.get("tags", []),
                    "addOptions": {
                        "searchForMovie": True
                    }
                }

                response = requests.post(
                    f"{dest_config['url']}/api/v3/movie",
                    headers=headers,
                    json=data,
                    timeout=30
                )
                response.raise_for_status()
                print(f"Added movie '{movie['title']}' to Radarr instance")
            except requests.exceptions.RequestException as e:
                print(f"Error adding movie '{movie['title']}': {e}")
                success = False

        return success

    def sync_shows_to_sonarr(self, shows: List[Dict[str, Any]], dest_config: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Sync shows to a Sonarr instance with enhanced filtering."""
        headers = {
            "X-Api-Key": dest_config["api_key"],
            "Content-Type": "application/json"
        }

        success = True
        for show in shows:
            if not self.apply_filters(show, filters):
                continue

            try:
                # Search for the series first
                search_response = requests.get(
                    f"{dest_config['url']}/api/v3/series/lookup",
                    headers=headers,
                    params={"term": f"tvdb:{show['id']}"},
                    timeout=30
                )
                search_response.raise_for_status()
                search_results = search_response.json()

                if search_results:
                    series_data = search_results[0]
                    data = {
                        "tvdbId": show["id"],
                        "title": series_data["title"],
                        "qualityProfileId": show.get("quality_profile", 1),
                        "rootFolderPath": show.get("root_folder", "/tv"),
                        "seasonFolder": True,
                        "monitored": True,
                        "tags": show.get("tags", []),
                        "addOptions": {
                            "searchForMissingEpisodes": True
                        }
                    }

                    response = requests.post(
                        f"{dest_config['url']}/api/v3/series",
                        headers=headers,
                        json=data,
                        timeout=30
                    )
                    response.raise_for_status()
                    print(f"Added show '{show['title']}' to Sonarr instance")
                else:
                    print(f"Show '{show['title']}' not found in Sonarr lookup")
                    success = False
            except requests.exceptions.RequestException as e:
                print(f"Error adding show '{show['title']}': {e}")
                success = False

        return success

def main():
    manager = MediaServerManager()
    
    while True:
        print("\nOptions:")
        print("1. Add a new media server instance")
        print("2. Remove a media server instance")
        print("3. Perform manual backup")
        print("4. Perform manual sync")
        print("5. Restore from backup")
        print("6. View configured instances")
        print("7. Exit")
        
        choice = input("Enter your choice (1-7): ")

        if choice == '1':
            name = input("Enter a name for the instance: ")
            url = input(f"Enter the URL for {name}: ").strip()
            api_key = input(f"Enter the API key for {name}: ").strip()
            instance_type = input("Enter instance type (radarr/sonarr): ").strip().lower()
            
            # Backup configuration
            backup_enabled = input("Enable automatic backup? (y/n): ").lower() == 'y'
            backup_config = None
            if backup_enabled:
                schedule_type = input("Enter backup schedule type (daily/weekly/monthly/cron): ").strip().lower()
                if schedule_type == 'cron':
                    cron = input("Enter cron expression: ").strip()
                    backup_config = {
                        "enabled": True,
                        "schedule": {"type": "cron", "cron": cron}
                    }
                else:
                    time = input("Enter backup time (HH:MM): ").strip()
                    backup_config = {
                        "enabled": True,
                        "schedule": {"type": schedule_type, "time": time}
                    }

            # Sync configuration
            sync_enabled = input("Configure sync from parent? (y/n): ").lower() == 'y'
            sync_config = None
            if sync_enabled:
                parent = input("Enter parent instance name: ").strip()
                schedule_type = input("Enter sync schedule type (daily/weekly/monthly/cron): ").strip().lower()
                if schedule_type == 'cron':
                    cron = input("Enter cron expression: ").strip()
                    sync_config = {
                        "parent_instance": parent,
                        "schedule": {"type": "cron", "cron": cron}
                    }
                else:
                    time = input("Enter sync time (HH:MM): ").strip()
                    sync_config = {
                        "parent_instance": parent,
                        "schedule": {"type": schedule_type, "time": time}
                    }

            # Filters configuration
            filters = {}
            if input("Configure filters? (y/n): ").lower() == 'y':
                quality_profiles = input("Enter quality profile IDs (comma-separated, leave empty to skip): ").strip()
                if quality_profiles:
                    filters["quality_profiles"] = [qp.strip() for qp in quality_profiles.split(",")]

                root_folders = input("Enter root folders (comma-separated, leave empty to skip): ").strip()
                if root_folders:
                    filters["root_folders"] = [rf.strip() for rf in root_folders.split(",")]

                tags = input("Enter tags (comma-separated, leave empty to skip): ").strip()
                if tags:
                    filters["tags"] = [tag.strip() for tag in tags.split(",")]

                min_year = input("Enter minimum year (leave empty to skip): ").strip()
                if min_year:
                    filters["min_year"] = int(min_year)

            if manager.add_instance(name, url, api_key, instance_type, backup_config, sync_config, filters):
                manager.save_instances()
                print(f"Instance {name} added successfully.")
            else:
                print(f"Failed to add instance {name}.")

        elif choice == '2':
            if not manager.instances:
                print("No instances configured to remove.")
                continue

            print("\nAvailable instances:")
            for i, name in enumerate(manager.instances.keys(), 1):
                print(f"{i}. {name} ({manager.instances[name]['type']})")

            try:
                index = int(input("Enter the number of the instance to remove: ")) - 1
                if 0 <= index < len(manager.instances):
                    name = list(manager.instances.keys())[index]
                    del manager.instances[name]
                    manager.save_instances()
                    print(f"Removed instance: {name}")
                else:
                    print("Invalid instance number.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == '3':
            if not manager.instances:
                print("No instances configured for backup.")
                continue

            print("\nAvailable instances:")
            for i, name in enumerate(manager.instances.keys(), 1):
                print(f"{i}. {name} ({manager.instances[name]['type']})")

            try:
                index = int(input("Enter the number of the instance to backup: ")) - 1
                if 0 <= index < len(manager.instances):
                    name = list(manager.instances.keys())[index]
                    if manager.manual_backup(name):
                        print("Backup completed successfully.")
                    else:
                        print("Backup failed.")
                else:
                    print("Invalid instance number.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == '4':
            if not manager.instances:
                print("No instances configured for syncing.")
                continue

            print("\nAvailable source instances:")
            for i, name in enumerate(manager.instances.keys(), 1):
                print(f"{i}. {name} ({manager.instances[name]['type']})")

            try:
                source_index = int(input("Enter the number of the source instance: ")) - 1
                if 0 <= source_index < len(manager.instances):
                    source_name = list(manager.instances.keys())[source_index]
                    source_type = manager.instances[source_name]['type']

                    print("\nAvailable destination instances:")
                    dest_instances = [
                        (i, name) for i, name in enumerate(manager.instances.keys(), 1)
                        if name != source_name and manager.instances[name]['type'] == source_type
                    ]

                    if not dest_instances:
                        print(f"No compatible destination instances found for {source_type}.")
                        continue

                    for i, name in dest_instances:
                        print(f"{i}. {name}")

                    dest_index = int(input("Enter the number of the destination instance: ")) - 1
                    if 0 <= dest_index < len(dest_instances):
                        dest_name = dest_instances[dest_index][1]
                        if manager.manual_sync(source_name, dest_name):
                            print("Sync completed successfully.")
                        else:
                            print("Sync failed.")
                    else:
                        print("Invalid destination instance number.")
                else:
                    print("Invalid source instance number.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == '5':
            if not manager.instances:
                print("No instances configured for restore.")
                continue

            print("\nAvailable backup instances:")
            for i, name in enumerate(manager.instances.keys(), 1):
                print(f"{i}. {name} ({manager.instances[name]['type']})")

            try:
                backup_index = int(input("Enter the number of the backup instance: ")) - 1
                if 0 <= backup_index < len(manager.instances):
                    backup_name = list(manager.instances.keys())[backup_index]
                    backup_type = manager.instances[backup_name]['type']

                    print("\nAvailable destination instances:")
                    dest_instances = [
                        (i, name) for i, name in enumerate(manager.instances.keys(), 1)
                        if manager.instances[name]['type'] == backup_type
                    ]

                    if not dest_instances:
                        print(f"No compatible destination instances found for {backup_type}.")
                        continue

                    for i, name in dest_instances:
                        print(f"{i}. {name}")

                    dest_index = int(input("Enter the number of the destination instance: ")) - 1
                    if 0 <= dest_index < len(dest_instances):
                        dest_name = dest_instances[dest_index][1]
                        if manager.restore_from_backup(backup_name, dest_name):
                            print("Restore completed successfully.")
                        else:
                            print("Restore failed.")
                    else:
                        print("Invalid destination instance number.")
                else:
                    print("Invalid backup instance number.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == '6':
            if not manager.instances:
                print("No instances configured.")
            else:
                print("\nConfigured instances:")
                for name, config in manager.instances.items():
                    print(f"\nName: {name}")
                    print(f"Type: {config['type']}")
                    print(f"URL: {config['url']}")
                    
                    if config.get('backup', {}).get('enabled'):
                        backup_schedule = config['backup']['schedule']
                        print("Backup: Enabled")
                        print(f"Backup Schedule: {backup_schedule['type']}")
                        if backup_schedule['type'] == 'cron':
                            print(f"Backup Cron: {backup_schedule['cron']}")
                        else:
                            print(f"Backup Time: {backup_schedule['time']}")
                    else:
                        print("Backup: Disabled")

                    if config.get('sync', {}).get('parent_instance'):
                        print(f"Sync Parent: {config['sync']['parent_instance']}")
                        if config['sync'].get('schedule'):
                            sync_schedule = config['sync']['schedule']
                            print(f"Sync Schedule: {sync_schedule['type']}")
                            if sync_schedule['type'] == 'cron':
                                print(f"Sync Cron: {sync_schedule['cron']}")
                            else:
                                print(f"Sync Time: {sync_schedule['time']}")

                    if config.get('filters'):
                        print("Filters:")
                        for filter_name, filter_value in config['filters'].items():
                            print(f"  {filter_name}: {filter_value}")

        elif choice == '7':
            break

        else:
            print("Invalid choice. Please enter a number between 1 and 7.")

if __name__ == "__main__":
    main()
