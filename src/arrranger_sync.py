#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
# "requests",
# "croniter",
# "schedule",
# ]
# ///

"""
Arrranger Sync Module

Core functionality for managing media server instances, database operations,
API interactions, and synchronization between Radarr and Sonarr instances.
This module serves as the backbone of the Arrranger application, providing
the essential components for backing up and synchronizing media libraries.
"""
import sqlite3
import requests
import json
import os
import time
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime
from croniter import croniter
from src.arrranger_logging import log_backup_operation, log_sync_operation

CONFIG_FILE = os.environ.get("CONFIG_FILE", "arrranger_instances.json")
DB_NAME = os.environ.get("DB_NAME", "arrranger.db")

class DatabaseManager:
    """
    Manages database operations for the Arrranger application.
    
    Handles SQLite database initialization, connections, and operations for storing
    and retrieving media data and release history. Provides methods for tracking
    media items across instances and maintaining a reliable backup of library data.
    
    The database schema includes tables for instances, movies, shows, and release
    history, with appropriate indexes for efficient querying.
    """
    
    def __init__(self, db_name: str = DB_NAME):
        """
        Initialize the database manager.
        
        Args:
            db_name: Name/path of the SQLite database file
        """
        self.db_name = db_name
        self.init_database()
    
    def connect(self) -> sqlite3.Connection:
        """
        Create and return a database connection.
        
        Returns:
            sqlite3.Connection: An active connection to the SQLite database
        """
        return sqlite3.connect(self.db_name)

    def init_database(self) -> None:
        """
        Initialize database tables with the required schema.
        
        Creates all necessary tables if they don't exist, including:
        - instances: Tracks media server instances
        - movies: Stores movie metadata from Radarr instances
        - shows: Stores show metadata from Sonarr instances
        - ReleaseHistory: Stores release history for media items
        """
        conn = self.connect()
        cursor = conn.cursor()

        # Create instances table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        # Create movies table
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

        # Create shows table
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

        # Create release history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ReleaseHistory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id INTEGER NOT NULL,
                media_type TEXT NOT NULL, -- 'movie' or 'episode'
                media_item_id INTEGER NOT NULL, -- Corresponds to movie.id or episode.id
                history_event_id INTEGER NOT NULL, -- Original history ID from Sonarr/Radarr
                event_type TEXT NOT NULL,
                date TEXT NOT NULL, -- ISO 8601 format
                source_title TEXT,
                indexer TEXT,
                download_client TEXT,
                guid TEXT,
                info_hash TEXT,
                download_id TEXT,
                quality_json TEXT, -- JSON representation of QualityModel
                custom_formats_json TEXT, -- JSON array of CustomFormatResource
                custom_format_score INTEGER,
                backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (instance_id) REFERENCES instances(id),
                UNIQUE (instance_id, history_event_id) -- Prevent duplicate history entries per instance
            )
        """)

        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_releasehistory_instance_media ON ReleaseHistory (instance_id, media_type, media_item_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_releasehistory_event ON ReleaseHistory (instance_id, history_event_id)")

        conn.commit()
        conn.close()

    def get_media_count(self, instance_name: str, media_type: str) -> int:
        """
        Get count of media items for an instance.
        
        Args:
            instance_name: Name of the instance
            media_type: Type of media ("movie" or "show")
            
        Returns:
            int: Count of media items for the specified instance
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        table = "movies" if media_type == "movie" else "shows"
        instance_field = "radarr_instance" if media_type == "movie" else "sonarr_instance"
        
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {instance_field} = ?", (instance_name,))
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            print(f"Error getting media count: {e}")
            return 0
        finally:
            conn.close()

    def get_or_create_instance_id(self, instance_name: str) -> Optional[int]:
        """
        Get the database ID for an instance name, creating it if it doesn't exist.
        
        Args:
            instance_name: Name of the instance
            
        Returns:
            Optional[int]: Database ID for the instance, or None if an error occurred
        """
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM instances WHERE name = ?", (instance_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                cursor.execute("INSERT INTO instances (name) VALUES (?)", (instance_name,))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database error getting/creating instance ID for {instance_name}: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def save_media(self, instance_name: str, media_type: str, media_data: List[Dict[str, Any]]) -> Tuple[int, int, int, int]:
        """
        Save media data to database with enhanced metadata.
        
        This function ensures the database exactly reflects the current state of the instance
        by adding new media and removing media that no longer exists in the instance.
        
        Args:
            instance_name: Name of the instance the media belongs to
            media_type: Type of media ("movie" or "show")
            media_data: List of media items from the API
            
        Returns:
            Tuple[int, int, int, int]: (current count, previous count, added count, removed count)
        """
        previous_count = self.get_media_count(instance_name, media_type)
        
        conn = self.connect()
        cursor = conn.cursor()

        # Determine field names based on media type
        id_field = "tmdb_id" if media_type == "movie" else "tvdb_id"
        instance_field = "radarr_instance" if media_type == "movie" else "sonarr_instance"
        table = "movies" if media_type == "movie" else "shows"
        
        # Get existing IDs from database
        cursor.execute(f"SELECT {id_field} FROM {table} WHERE {instance_field} = ?", (instance_name,))
        existing_ids = {row[0] for row in cursor.fetchall()}

        # Get IDs from incoming data
        incoming_id_field = "tmdbId" if media_type == "movie" else "tvdbId"
        incoming_ids = {item.get(incoming_id_field) for item in media_data if item.get(incoming_id_field) is not None}

        # Calculate differences
        to_add = incoming_ids - existing_ids
        to_remove = existing_ids - incoming_ids
        
        added_count = len(to_add)
        removed_count = len(to_remove)
        
        try:
            # Handle case where all media is removed
            if not incoming_ids:
                cursor.execute(f"DELETE FROM {table} WHERE {instance_field} = ?", (instance_name,))
                return 0, previous_count, 0, previous_count

            # Remove items that no longer exist in the source
            if to_remove:
                placeholders = ','.join('?' for _ in to_remove)
                cursor.execute(
                    f"DELETE FROM {table} WHERE {instance_field} = ? AND {id_field} IN ({placeholders})",
                    [instance_name] + list(to_remove)
                )

            # Insert or update media items
            if media_type == "movie":
                self._save_movies(cursor, instance_name, media_data)
            elif media_type == "show":
                self._save_shows(cursor, instance_name, media_data)

            conn.commit()
            current_count = len(incoming_ids)
            
            return current_count, previous_count, added_count, removed_count
        except sqlite3.Error as e:
            print(f"Database error saving media for {instance_name}: {e}")
            conn.rollback()
            return 0, previous_count, 0, 0
        finally:
            conn.close()
            
    def _save_movies(self, cursor: sqlite3.Cursor, instance_name: str, media_data: List[Dict[str, Any]]) -> None:
        """
        Save movie data to the database.
        
        Args:
            cursor: Active database cursor
            instance_name: Name of the Radarr instance
            media_data: List of movie items from Radarr API
        """
        for item in media_data:
            media_id = item.get("tmdbId")
            if media_id is not None:
                cursor.execute("""
                    INSERT OR REPLACE INTO movies
                    (radarr_instance, title, year, tmdb_id, quality_profile, root_folder, tags, backup_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    instance_name,
                    item.get("title"),
                    item.get("year"),
                    media_id,
                    item.get("qualityProfileId"),
                    item.get("rootFolderPath"),
                    ','.join(str(tag) for tag in item.get("tags", []))
                ))
                
    def _save_shows(self, cursor: sqlite3.Cursor, instance_name: str, media_data: List[Dict[str, Any]]) -> None:
        """
        Save show data to the database.
        
        Args:
            cursor: Active database cursor
            instance_name: Name of the Sonarr instance
            media_data: List of show items from Sonarr API
        """
        for item in media_data:
            media_id = item.get("tvdbId")
            if media_id is not None:
                cursor.execute("""
                    INSERT OR REPLACE INTO shows
                    (sonarr_instance, title, year, tvdb_id, quality_profile, root_folder, tags, backup_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    instance_name,
                    item.get("title"),
                    item.get("year"),
                    media_id,
                    item.get("qualityProfileId"),
                    item.get("rootFolderPath"),
                    ','.join(str(tag) for tag in item.get("tags", []))
                ))

    def get_media(self, instance_name: str, media_type: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Retrieve media data from database with filter support.
        
        Args:
            instance_name: Name of the instance to get media for
            media_type: Type of media ("movie" or "show")
            filters: Optional dictionary of filters to apply
            
        Returns:
            List[Dict[str, Any]]: List of media items matching the criteria
        """
        conn = self.connect()
        cursor = conn.cursor()

        try:
            # Build the base query
            base_query = """
                SELECT title, year, {id_field}, quality_profile, root_folder, tags
                FROM {table}
                WHERE {instance_field} = ?
            """

            params = [instance_name]
            conditions = []

            # Apply filters if provided
            if filters:
                conditions, params = self._apply_filters_to_query(filters, params)

            # Add filter conditions to query if any exist
            if conditions:
                base_query += " AND " + " AND ".join(conditions)

            # Format query based on media type
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

            # Execute query and process results
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return self._process_media_rows(rows)
        finally:
            conn.close()
            
    def _apply_filters_to_query(self, filters: Dict[str, Any], params: List[Any]) -> Tuple[List[str], List[Any]]:
        """
        Apply filters to a database query.
        
        Args:
            filters: Dictionary of filters to apply
            params: List of existing query parameters
            
        Returns:
            Tuple[List[str], List[Any]]: Tuple of (conditions, updated_params)
        """
        conditions = []
        
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
            
        return conditions, params
        
    def _process_media_rows(self, rows: List[Tuple]) -> List[Dict[str, Any]]:
        """
        Process database rows into media item dictionaries.
        
        Args:
            rows: List of database result rows
            
        Returns:
            List[Dict[str, Any]]: List of media items as dictionaries
        """
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

    def save_release_history(self, instance_name: str, instance_db_id: int, media_type: str,
                            media_item_id: int, history_data: List[Dict[str, Any]]) -> int:
        """
        Save release history records to the database, ignoring duplicates.
        
        Args:
            instance_name: Name of the instance (for logging)
            instance_db_id: Database ID of the instance
            media_type: Type of media ("movie" or "show")
            media_item_id: Internal ID of the media item in Sonarr/Radarr
            history_data: List of history records from the API
            
        Returns:
            int: Number of records added
        """
        conn = self.connect()
        cursor = conn.cursor()
        added_count = 0

        # Define relevant event types to store
        relevant_event_types = {'grabbed', 'downloadFolderImported'}

        try:
            for record in history_data:
                # Skip irrelevant event types
                event_type = record.get('eventType')
                if event_type not in relevant_event_types:
                    continue

                # Skip records without an ID
                history_event_id = record.get('id')
                if history_event_id is None:
                    continue

                # Process record data
                data_dict = record.get('data', {})
                quality_json = json.dumps(record.get('quality')) if record.get('quality') else None
                custom_formats_json = json.dumps(record.get('customFormats')) if record.get('customFormats') else None

                # Insert record, ignoring duplicates
                cursor.execute("""
                    INSERT OR IGNORE INTO ReleaseHistory
                    (instance_id, media_type, media_item_id, history_event_id, event_type,
                     date, source_title, indexer, download_client, guid, info_hash,
                     download_id, quality_json, custom_formats_json, custom_format_score, backup_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    instance_db_id,
                    media_type,
                    media_item_id,
                    history_event_id,
                    event_type,
                    record.get('date'),
                    record.get('sourceTitle'),
                    data_dict.get('indexer'),
                    data_dict.get('downloadClient'),
                    data_dict.get('guid'),
                    data_dict.get('infoHash'),
                    data_dict.get('downloadId'),
                    quality_json,
                    custom_formats_json,
                    record.get('customFormatScore')
                ))
                added_count += cursor.rowcount
            
            conn.commit()
            return added_count
        except sqlite3.Error as e:
            print(f"Database error saving release history for {instance_name}: {e}")
            conn.rollback()
            return 0
        except json.JSONDecodeError as e:
            print(f"JSON error processing history data for {instance_name}: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def get_release_history(self, instance_db_id: int) -> List[Dict[str, Any]]:
        """
        Retrieve all release history records for a given instance ID.
        
        Args:
            instance_db_id: Database ID of the instance
            
        Returns:
            List[Dict[str, Any]]: List of release history records
        """
        conn = self.connect()
        cursor = conn.cursor()
        results = []
        try:
            cursor.execute("""
                SELECT
                    id, instance_id, media_type, media_item_id, history_event_id,
                    event_type, date, source_title, indexer, download_client,
                    guid, info_hash, download_id, quality_json,
                    custom_formats_json, custom_format_score, backup_date
                FROM ReleaseHistory
                WHERE instance_id = ?
                ORDER BY date DESC
            """, (instance_db_id,))
            
            # Convert rows to dictionaries using column names
            columns = [description[0] for description in cursor.description]
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
        except sqlite3.Error as e:
            print(f"Database error retrieving release history for instance ID {instance_db_id}: {e}")
            return []
        finally:
            conn.close()

class ApiClient:
    """
    Handles API communication with Sonarr and Radarr instances.
    
    Provides methods for making API requests to media server instances with
    proper error handling and response processing. Implements connection verification,
    data fetching, and standardized request patterns to ensure consistent
    interaction with the Radarr/Sonarr API endpoints.
    
    Features timeout management and detailed error reporting to improve
    reliability when communicating with potentially unstable network services.
    """
    
    def __init__(self):
        """Initialize the API client."""
        self.timeout_short = 10  # Short timeout for simple operations
        self.timeout_long = 30   # Longer timeout for operations that might take more time
    
    def make_request(self, url: str, headers: Dict[str, str], method: str = "GET",
                    params: Optional[Dict[str, Any]] = None,
                    json_data: Optional[Dict[str, Any]] = None,
                    timeout: Optional[int] = None) -> Optional[Any]:
        """
        Make an API request to the media server with error handling.
        
        Args:
            url: The full URL for the API endpoint
            headers: Request headers including API key
            method: HTTP method (GET, POST, DELETE)
            params: URL parameters for the request
            json_data: JSON data for POST requests
            timeout: Request timeout in seconds (uses default if None)
            
        Returns:
            Optional[Any]: Response JSON data or None if request failed
        """
        if timeout is None:
            timeout = self.timeout_short
            
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method == "POST":
                response = requests.post(url, headers=headers, params=params, json=json_data, timeout=timeout)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, params=params, timeout=timeout)
            else:
                print(f"Unsupported HTTP method: {method}")
                return None
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e, url)
            return None
        except requests.exceptions.ConnectionError:
            print(f"Connection error: Could not connect to {url}")
            print("Please verify the server is running and accessible")
            return None
        except requests.exceptions.Timeout:
            print(f"Timeout error: Connection to {url} timed out after {timeout}s")
            print("Please verify the server is responding properly")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
    
    def _handle_http_error(self, error: requests.exceptions.HTTPError, url: str) -> None:
        """
        Handle HTTP errors with detailed messages.
        
        Args:
            error: The HTTP error that occurred
            url: The URL that was requested
        """
        if error.response.status_code == 401:
            print(f"Authentication error: Invalid API key or insufficient permissions")
            print(f"Please verify the API key in your configuration")
        elif error.response.status_code == 404:
            print(f"Error: API endpoint not found: {url}")
            print(f"Please verify the URL in your configuration")
        else:
            print(f"HTTP error: {error}")
            
        try:
            error_details = error.response.json()
            print(f"Error details: {error_details}")
        except:
            pass
    
    def verify_connection(self, url: str, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Verify connection to a media server instance.
        
        Args:
            url: Base URL of the media server
            api_key: API key for authentication
            
        Returns:
            Optional[Dict[str, Any]]: System status information or None if connection failed
        """
        headers = {"X-Api-Key": api_key}
        status_url = f"{url}/api/v3/system/status"
        
        return self.make_request(status_url, headers=headers, timeout=self.timeout_short)
    
    def fetch_quality_profiles(self, url: str, api_key: str) -> List[Dict[str, Any]]:
        """
        Fetch quality profiles from a media server instance.
        
        Args:
            url: Base URL of the media server
            api_key: API key for authentication
            
        Returns:
            List[Dict[str, Any]]: List of quality profiles or empty list if request failed
        """
        headers = {"X-Api-Key": api_key}
        profiles_url = f"{url}/api/v3/qualityprofile"
        
        result = self.make_request(profiles_url, headers=headers, timeout=self.timeout_long)
        if result is None:
            print(f"Failed to fetch quality profiles from {url}")
            return []
        return result
    
    def fetch_root_folders(self, url: str, api_key: str) -> List[Dict[str, Any]]:
        """
        Fetch root folders from a media server instance.
        
        Args:
            url: Base URL of the media server
            api_key: API key for authentication
            
        Returns:
            List[Dict[str, Any]]: List of root folders or empty list if request failed
        """
        headers = {"X-Api-Key": api_key}
        folders_url = f"{url}/api/v3/rootfolder"
        
        result = self.make_request(folders_url, headers=headers, timeout=self.timeout_long)
        if result is None:
            print(f"Failed to fetch root folders from {url}")
            return []
        return result
    
    def fetch_tags(self, url: str, api_key: str) -> List[Dict[str, Any]]:
        """
        Fetch tags from a media server instance.
        
        Args:
            url: Base URL of the media server
            api_key: API key for authentication
            
        Returns:
            List[Dict[str, Any]]: List of tags or empty list if request failed
        """
        headers = {"X-Api-Key": api_key}
        tags_url = f"{url}/api/v3/tag"
        
        result = self.make_request(tags_url, headers=headers, timeout=self.timeout_long)
        if result is None:
            print(f"Failed to fetch tags from {url}")
            return []
        return result


class ConfigManager:
    """
    Manages configuration for media server instances.
    
    Handles loading, saving, and validating configuration for media server instances
    from a JSON configuration file. Ensures that schedule configurations use valid
    cron expressions and maintains the integrity of the configuration data.
    
    The configuration includes server connection details, backup and sync schedules,
    and filtering rules for media selection.
    """
    
    def __init__(self, config_file: str = CONFIG_FILE):
        """
        Initialize the configuration manager.
        
        Args:
            config_file: Path to the configuration file
        """
        self.config_file = config_file
    
    def load_instances(self) -> Dict[str, Dict[str, Any]]:
        """
        Load media server instances from config file.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of configured instances
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error loading config file: {e}")
                return {}
        return {}

    def save_instances(self, instances: Dict[str, Dict[str, Any]]) -> bool:
        """
        Save media server instances to config file.
        
        Args:
            instances: Dictionary of instances to save
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            with open(self.config_file, "w") as f:
                json.dump(instances, f, indent=4)
            print("Media server instances configuration saved.")
            return True
        except IOError as e:
            print(f"Error saving config file: {e}")
            return False

    def validate_schedule(self, schedule: Dict[str, Any]) -> bool:
        """
        Validate schedule configuration.
        
        Only cron scheduling is currently supported.
        
        Args:
            schedule: Schedule configuration to validate
            
        Returns:
            bool: True if schedule is valid, False otherwise
        """
        if not isinstance(schedule, dict):
            return False

        if schedule.get("type") != "cron":
            print("Warning: Only cron scheduling is supported")
            return False

        if not schedule.get("cron") or not croniter.is_valid(schedule["cron"]):
            print("Error: Invalid cron expression")
            return False

        return True


class MediaServerManager:
    """
    Manages media server instances and operations.
    
    Acts as the central coordinator for operations between media server instances,
    including backups, syncs, and API interactions. Integrates the database manager,
    API client, and configuration manager to provide a unified interface for
    managing Radarr and Sonarr instances.
    
    Handles instance validation, metadata retrieval, and provides methods for
    adding, removing, and configuring server instances.
    """
    
    def __init__(self):
        """Initialize the media server manager with required components."""
        self.db_manager = DatabaseManager()
        self.api_client = ApiClient()
        self.config_manager = ConfigManager()
        self.instances = self.config_manager.load_instances()

    def save_instances(self) -> bool:
        """
        Save current instances configuration to file.
        
        Returns:
            bool: True if save was successful, False otherwise
        """
        return self.config_manager.save_instances(self.instances)

    def add_instance(self, name: str, url: str, api_key: str, instance_type: str,
                    backup_config: Optional[Dict[str, Any]] = None,
                    sync_config: Optional[Dict[str, Any]] = None,
                    filters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a new media server instance with enhanced configuration.
        
        Args:
            name: Name for the instance
            url: Base URL of the media server
            api_key: API key for authentication
            instance_type: Type of instance ("radarr" or "sonarr")
            backup_config: Configuration for backups
            sync_config: Configuration for syncs
            filters: Filters to apply to media
            
        Returns:
            bool: True if instance was added successfully, False otherwise
        """
        # Ensure URL has proper protocol
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        # Validate backup schedule if enabled
        if backup_config and backup_config.get("enabled"):
            if not self.config_manager.validate_schedule(backup_config.get("schedule", {})):
                print("Invalid backup schedule configuration")
                return False

        # Validate sync configuration
        if sync_config:
            if sync_config.get("parent_instance") and sync_config.get("parent_instance") not in self.instances:
                print(f"Parent instance {sync_config['parent_instance']} not found")
                return False
            if sync_config.get("schedule") and not self.config_manager.validate_schedule(sync_config["schedule"]):
                print("Invalid sync schedule configuration")
                return False

        try:
            # Verify connection to the media server
            system_status = self.api_client.verify_connection(url, api_key)
            if not system_status:
                return False
                
            print(f"Successfully connected to {instance_type.capitalize()} v{system_status.get('version', 'unknown')}")

            # Fetch instance metadata
            quality_profiles = self.api_client.fetch_quality_profiles(url, api_key)
            if not quality_profiles:
                print(f"Warning: No quality profiles found in {instance_type}. You may need to configure one.")

            root_folders = self.api_client.fetch_root_folders(url, api_key)
            if not root_folders:
                print(f"Warning: No root folders found in {instance_type}. You will need to add one before syncing.")

            tags = self.api_client.fetch_tags(url, api_key)

            # Create instance configuration
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

class BackupManager:
    """
    Manages backup operations for media server instances.
    
    Handles the process of backing up media data and release history from
    Radarr and Sonarr instances to the local SQLite database. Implements
    differential backup logic to track added and removed items between
    backup operations.
    
    The backup process includes fetching current media data, comparing with
    previously stored data, and optionally backing up detailed release history
    for potential future restoration.
    """
    
    def __init__(self, db_manager: DatabaseManager, api_client: ApiClient):
        """
        Initialize the backup manager.
        
        Args:
            db_manager: Database manager for storing backup data
            api_client: API client for fetching data from media servers
        """
        self.db_manager = db_manager
        self.api_client = api_client
    
    def backup_media(self, instance_name: str, instance_config: Dict[str, Any]) -> bool:
        """
        Perform a complete backup of a media server instance.
        
        This includes backing up all media items and optionally release history.
        
        Args:
            instance_name: Name of the instance to back up
            instance_config: Configuration for the instance
            
        Returns:
            bool: True if backup was successful, False otherwise
        """
        try:
            # Determine media type based on instance type
            media_type = "movie" if instance_config["type"] == "radarr" else "show"
            
            # Fetch media data from the server
            media_data = self._fetch_media_data(instance_name, instance_config)
            if not media_data:
                self._log_failed_backup(instance_name, "No media data retrieved")
                return False
                
            # Save media data to database
            backup_result = self._save_media_data(instance_name, media_type, media_data)
            
            # Backup release history if enabled
            if instance_config.get("backup_release_history", False):
                self._backup_release_history(instance_name, instance_config, media_type, media_data)
                
            return backup_result
        except Exception as e:
            self._log_failed_backup(instance_name, str(e))
            print(f"Error during backup of {instance_name}: {e}")
            return False
    
    def _fetch_media_data(self, instance_name: str, instance_config: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch media data from a server instance.
        
        Args:
            instance_name: Name of the instance
            instance_config: Configuration for the instance
            
        Returns:
            Optional[List[Dict[str, Any]]]: List of media items or None if fetch failed
        """
        url = instance_config["url"]
        api_key = instance_config["api_key"]
        media_type = "movie" if instance_config["type"] == "radarr" else "series"
        
        # First verify system status to ensure server is responsive
        if not self.api_client.verify_connection(url, api_key):
            print(f"Failed to connect to {instance_name}")
            return None
        
        # Then fetch media data
        return self.api_client.fetch_media(url, api_key, media_type)
    
    def _save_media_data(self, instance_name: str, media_type: str, media_data: List[Dict[str, Any]]) -> bool:
        """
        Save media data to database and log results.
        
        Args:
            instance_name: Name of the instance
            media_type: Type of media ("movie" or "show")
            media_data: List of media items
            
        Returns:
            bool: True if save was successful
        """
        current_count, previous_count, added_count, removed_count = self.db_manager.save_media(
            instance_name, media_type, media_data
        )
        
        log_backup_operation(
            instance_name=instance_name,
            success=True,
            media_type=media_type,
            media_count=current_count,
            prev_media_count=previous_count,
            added_count=added_count,
            removed_count=removed_count
        )
        
        print(f"Backup of {instance_name} completed successfully: "
              f"{current_count} {media_type}s, {added_count} added, {removed_count} removed")
              
        return True
    
    def _backup_release_history(self, instance_name: str, instance_config: Dict[str, Any],
                               media_type: str, media_data: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Backup release history for media items.
        
        Fetches and stores the release history for each media item, which includes
        information about downloads, imports, and other events.
        
        Args:
            instance_name: Name of the instance
            instance_config: Configuration for the instance
            media_type: Type of media ("movie" or "show")
            media_data: List of media items
            
        Returns:
            Tuple[int, int]: Count of (added_records, error_count)
        """
        print(f"Starting release history backup for {instance_name}...")
        instance_db_id = self.db_manager.get_or_create_instance_id(instance_name)
        
        if instance_db_id is None:
            print(f"Error: Could not get or create database ID for instance {instance_name}. Skipping history backup.")
            return 0, 0
            
        history_added_count = 0
        history_error_count = 0
        
        for media_item in media_data:
            media_item_internal_id = media_item.get('id')  # Sonarr/Radarr internal ID
            if media_item_internal_id is None:
                continue
            
            try:
                history_data = self._fetch_history_for_media(
                    instance_name, instance_config, media_type, media_item_internal_id
                )
                if history_data:
                    added = self.db_manager.save_release_history(
                        instance_name,
                        instance_db_id,
                        media_type,
                        media_item_internal_id,
                        history_data
                    )
                    history_added_count += added
            except Exception as hist_e:
                print(f"Error fetching/saving history for {media_type} ID {media_item_internal_id}: {hist_e}")
                history_error_count += 1
        
        print(f"Release history backup for {instance_name} finished: {history_added_count} records added.")
        if history_error_count > 0:
            print(f"Warning: Encountered {history_error_count} errors during history backup.")
            
        return history_added_count, history_error_count
    
    def _fetch_history_for_media(self, instance_name: str, instance_config: Dict[str, Any],
                               media_type: str, media_item_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch history records for a specific media item.
        
        Args:
            instance_name: Name of the instance
            instance_config: Configuration for the instance
            media_type: Type of media ("movie" or "show")
            media_item_id: Internal ID of the media item
            
        Returns:
            Optional[List[Dict[str, Any]]]: List of history records or None if fetch failed
        """
        url = instance_config["url"]
        api_key = instance_config["api_key"]
        
        return self.api_client.fetch_history(url, api_key, media_type, media_item_id)
    
    def _log_failed_backup(self, instance_name: str, error_message: str) -> None:
        """
        Log a failed backup operation.
        
        Args:
            instance_name: Name of the instance
            error_message: Error message describing the failure
        """
        log_backup_operation(
            instance_name=instance_name,
            success=False,
            media_type="unknown",
            error=error_message
        )
        print(f"Backup failed for {instance_name}: {error_message}")


class SyncManager:
    """
    Manages synchronization operations between media server instances.
    
    Handles the synchronization of media items between Radarr or Sonarr instances,
    ensuring that destination instances match source instances according to
    specified filters and rules. Implements bidirectional comparison to determine
    which items need to be added or removed from the destination.
    
    Supports filtered synchronization based on quality profiles, root folders,
    tags, and other criteria. Also provides functionality for restoring from
    backups and retrieving release history.
    """
    
    def __init__(self, db_manager: DatabaseManager, api_client: ApiClient):
        """
        Initialize the sync manager.
        
        Args:
            db_manager: Database manager for accessing stored media data
            api_client: API client for interacting with media servers
        """
        self.db_manager = db_manager
        self.api_client = api_client
    
    def sync_instances(self, source_name: str, dest_name: str,
                      source_config: Dict[str, Any], dest_config: Dict[str, Any]) -> bool:
        """
        Synchronize media between two instances.
        
        Args:
            source_name: Name of the source instance
            dest_name: Name of the destination instance
            source_config: Configuration for the source instance
            dest_config: Configuration for the destination instance
            
        Returns:
            bool: True if sync was successful, False otherwise
        """
        try:
            # Verify instance types match
            if source_config["type"] != dest_config["type"]:
                self._log_failed_sync(source_name, dest_name,
                                     "Cannot sync between different types of instances")
                return False
                
            # Determine media type based on instance type
            media_type = "movie" if source_config["type"] == "radarr" else "show"
            
            # Fetch source media data
            source_media = self._fetch_media_data(source_name, source_config)
            if not source_media:
                self._log_failed_sync(source_name, dest_name,
                                     "No media data retrieved from source instance")
                return False
                
            # Fetch destination media data
            dest_media = self._fetch_media_data(dest_name, dest_config)
            if dest_media is None:
                self._log_failed_sync(source_name, dest_name,
                                     "Failed to retrieve media data from destination instance")
                return False
                
            # Apply filters and perform sync
            filters = dest_config.get("filters", {})
            success, added_count, removed_count, skipped_count = self._perform_sync(
                source_media, dest_media, dest_config, media_type, filters
            )
            
            # Log results
            self._log_sync_result(
                source_name, dest_name, success, media_type,
                added_count, removed_count, skipped_count
            )
            
            return success
        except Exception as e:
            self._log_failed_sync(source_name, dest_name, str(e))
            print(f"Error during sync: {e}")
            return False
    
    def _fetch_media_data(self, instance_name: str, instance_config: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch media data from a server instance.
        
        Args:
            instance_name: Name of the instance
            instance_config: Configuration for the instance
            
        Returns:
            Optional[List[Dict[str, Any]]]: List of media items or None if fetch failed
        """
        url = instance_config["url"]
        api_key = instance_config["api_key"]
        media_type = "movie" if instance_config["type"] == "radarr" else "series"
        
        # First verify system status to ensure server is responsive
        if not self.api_client.verify_connection(url, api_key):
            print(f"Failed to connect to {instance_name}")
            return None
        
        # Then fetch media data
        return self.api_client.fetch_media(url, api_key, media_type)
    
    def _perform_sync(self, source_media: List[Dict[str, Any]], dest_media: List[Dict[str, Any]],
                     dest_config: Dict[str, Any], media_type: str, filters: Dict[str, Any]) -> Tuple[bool, int, int, int]:
        """
        Perform sync operation between source and destination media lists.
        
        Determines which items to add and remove from the destination based on
        the source content and configured filters.
        
        Args:
            source_media: List of media items from source
            dest_media: List of media items from destination
            dest_config: Destination instance configuration
            media_type: Type of media (movie or show)
            filters: Filters to apply
            
        Returns:
            Tuple of (success, added_count, removed_count, skipped_count)
        """
        if media_type == "movie":
            return self.sync_movies_to_radarr(source_media, dest_media, dest_config, filters)
        else:
            return self.sync_shows_to_sonarr(source_media, dest_media, dest_config, filters)
    
    def _log_sync_result(self, source_name: str, dest_name: str, success: bool, media_type: str,
                        added_count: int, removed_count: int, skipped_count: int) -> None:
        """Log sync operation results."""
        log_sync_operation(
            parent_instance=source_name,
            child_instance=dest_name,
            success=success,
            media_type=media_type,
            added_count=added_count,
            removed_count=removed_count,
            skipped_count=skipped_count
        )
        
        print(f"Sync completed: {added_count} {media_type}s added, "
              f"{removed_count} removed, {skipped_count} skipped")

    def manual_sync(self, source_name: str, dest_name: str) -> bool:
        """Perform manual sync between instances."""
        source = self.instances.get(source_name)
        dest = self.instances.get(dest_name)

        if not source or not dest:
            error_msg = "Source or destination instance not found"
            log_sync_operation(
                parent_instance=source_name,
                child_instance=dest_name,
                success=False,
                media_type="unknown",
                error=error_msg
            )
            print(error_msg)
            return False

        if source["type"] != dest["type"]:
            error_msg = "Cannot sync between different types of instances"
            log_sync_operation(
                parent_instance=source_name,
                child_instance=dest_name,
                success=False,
                media_type="unknown",
                error=error_msg
            )
            print(error_msg)
            return False

        try:
            # Fetch source media data
            parent_media_data = self.fetch_media_data(source_name, source)
            if not parent_media_data:
                log_sync_operation(
                    parent_instance=source_name,
                    child_instance=dest_name,
                    success=False,
                    media_type="unknown",
                    error="No media data retrieved from parent instance"
                )
                return False

            # Fetch destination media data
            child_media_data = self.fetch_media_data(dest_name, dest)
            if child_media_data is None:
                log_sync_operation(
                    parent_instance=source_name,
                    child_instance=dest_name,
                    success=False,
                    media_type="unknown",
                    error="Failed to retrieve media data from child instance"
                )
                return False

            # Perform sync operation
            media_type = "movie" if source["type"] == "radarr" else "show"
            filters = dest.get("filters", {})
            
            success, added_count, removed_count, skipped_count = self._perform_sync(
                parent_media_data, child_media_data, dest, media_type, filters
            )
            
            # Log results
            self._log_sync_result(
                source_name, dest_name, success, media_type,
                added_count, removed_count, skipped_count
            )
            
            return success
        except Exception as e:
            error_msg = str(e)
            log_sync_operation(
                parent_instance=source_name,
                child_instance=dest_name,
                success=False,
                media_type="unknown",
                error=error_msg
            )
            print(f"Error during manual sync: {error_msg}")
            return False

    def restore_from_backup(self, backup_instance_name: str, dest_name: str) -> bool:
        """Restore media from database backup to an instance."""
        dest = self.instances.get(dest_name)
        if not dest:
            error_msg = f"Destination instance {dest_name} not found"
            log_sync_operation(
                parent_instance=backup_instance_name,
                child_instance=dest_name,
                success=False,
                media_type="unknown",
                error=error_msg
            )
            print(error_msg)
            return False

        try:
            media_type = "movie" if dest["type"] == "radarr" else "show"

            # Get media from backup
            backup_media = self.db_manager.get_media(backup_instance_name, media_type, dest.get("filters"))
            
            if not backup_media:
                error_msg = f"No media found in backup for {backup_instance_name}"
                log_sync_operation(
                    parent_instance=backup_instance_name,
                    child_instance=dest_name,
                    success=False,
                    media_type=media_type,
                    error=error_msg
                )
                print(error_msg)
                return False

            # Get destination media
            dest_media = self.fetch_media_data(dest_name, dest)
            if dest_media is None:
                log_sync_operation(
                    parent_instance=backup_instance_name,
                    child_instance=dest_name,
                    success=False,
                    media_type=media_type,
                    error="Failed to retrieve media data from destination instance"
                )
                return False

            # Perform sync operation
            success, added_count, removed_count, skipped_count = self._perform_sync(
                backup_media, dest_media, dest, media_type, dest.get("filters", {})
            )
            
            # Log results
            self._log_sync_result(
                backup_instance_name, dest_name, success, media_type,
                added_count, removed_count, skipped_count
            )
            
            return success
        except Exception as e:
            error_msg = str(e)
            log_sync_operation(
                parent_instance=backup_instance_name,
                child_instance=dest_name,
                success=False,
                media_type="unknown",
                error=error_msg
            )
            print(f"Error during restore from backup: {error_msg}")
            return False

    def _make_api_request(self, url: str, headers: Dict[str, str], method: str = "GET",
                         params: Optional[Dict[str, Any]] = None,
                         json_data: Optional[Dict[str, Any]] = None,
                         timeout: int = 30) -> Optional[Any]:
        """
        Make an API request to the media server with error handling.
        
        Args:
            url: The full URL for the API endpoint
            headers: Request headers including API key
            method: HTTP method (GET, POST, DELETE)
            params: URL parameters for the request
            json_data: JSON data for POST requests
            timeout: Request timeout in seconds
            
        Returns:
            Response JSON data or None if request failed
        """
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method == "POST":
                response = requests.post(url, headers=headers, params=params, json=json_data, timeout=timeout)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, params=params, timeout=timeout)
            else:
                print(f"Unsupported HTTP method: {method}")
                return None
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print(f"Authentication error: Invalid API key or insufficient permissions")
                print(f"Please verify the API key in your configuration")
            elif e.response.status_code == 404:
                print(f"Error: API endpoint not found: {url}")
                print(f"Please verify the URL in your configuration")
            else:
                print(f"HTTP error: {e}")
                
            try:
                error_details = e.response.json()
                print(f"Error details: {error_details}")
            except:
                pass
                
            return None
        except requests.exceptions.ConnectionError:
            print(f"Connection error: Could not connect to {url}")
            print("Please verify the server is running and accessible")
            return None
        except requests.exceptions.Timeout:
            print(f"Timeout error: Connection to {url} timed out")
            print("Please verify the server is responding properly")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
    
    def _get_instance_headers(self, instance_config: Dict[str, Any]) -> Dict[str, str]:
        """Create headers for API requests to an instance."""
        return {
            "X-Api-Key": instance_config["api_key"],
            "Content-Type": "application/json"
        }
    
    def _get_instance_url(self, instance_config: Dict[str, Any], endpoint: str) -> str:
        """Create a full URL for an API endpoint."""
        return f"{instance_config['url']}/api/v3/{endpoint}"
        
    def fetch_media_data(self, instance_name: str, instance_config: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Fetch media data from a server instance."""
        headers = self._get_instance_headers(instance_config)
        media_type = "movie" if instance_config["type"] == "radarr" else "series"
        
        # First verify system status
        status_url = self._get_instance_url(instance_config, "system/status")
        if self._make_api_request(status_url, headers=headers, timeout=10) is None:
            print(f"Failed to connect to {instance_name}")
            return None
        
        # Then fetch media data
        media_url = self._get_instance_url(instance_config, media_type)
        return self._make_api_request(media_url, headers=headers)

    def fetch_history_for_media(self, instance_name: str, instance_config: Dict[str, Any],
                               media_type: str, media_item_id: int) -> Optional[List[Dict[str, Any]]]:
        """Fetch history records for a specific media item from a server instance."""
        headers = self._get_instance_headers(instance_config)
        api_endpoint = "movie" if media_type == "movie" else "series"
        query_param = "movieId" if media_type == "movie" else "seriesId"
        
        history_url = self._get_instance_url(
            instance_config,
            f"history/{api_endpoint}"
        )
        
        result = self._make_api_request(
            history_url,
            headers=headers,
            params={query_param: media_item_id}
        )
        
        if result is None:
            print(f"Failed to fetch history for {media_type} ID {media_item_id} from {instance_name}")
            
        return result

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

    def sync_movies_to_radarr(self, parent_movies: List[Dict[str, Any]], child_movies: List[Dict[str, Any]],
                             dest_config: Dict[str, Any], filters: Dict[str, Any]) -> Tuple[bool, int, int, int]:
        """
        Sync movies to a Radarr instance with exact matching to parent.
        
        Args:
            parent_movies: List of movies from parent instance
            child_movies: List of movies from child instance
            dest_config: Destination instance configuration
            filters: Filters to apply
            
        Returns:
            Tuple of (success, added_count, removed_count, skipped_count)
        """
        headers = {
            "X-Api-Key": dest_config["api_key"],
            "Content-Type": "application/json"
        }

        success = True
        added_count = 0
        removed_count = 0
        skipped_count = 0

        parent_tmdb_ids = {movie.get("tmdbId") for movie in parent_movies if movie.get("tmdbId")}
        child_tmdb_ids = {movie.get("tmdbId") for movie in child_movies if movie.get("tmdbId")}

        child_movie_map = {movie.get("tmdbId"): movie for movie in child_movies if movie.get("tmdbId")}

        to_add = parent_tmdb_ids - child_tmdb_ids
        to_remove = child_tmdb_ids - parent_tmdb_ids
        
        print(f"Syncing movies: {len(to_add)} to add, {len(to_remove)} to remove")

        try:
            quality_profiles_response = requests.get(
                f"{dest_config['url']}/api/v3/qualityprofile",
                headers=headers,
                timeout=30
            )
            quality_profiles_response.raise_for_status()
            dest_quality_profiles = quality_profiles_response.json()

            root_folders_response = requests.get(
                f"{dest_config['url']}/api/v3/rootfolder",
                headers=headers,
                timeout=30
            )
            root_folders_response.raise_for_status()
            dest_root_folders = root_folders_response.json()

            dest_quality_profile_id = 1
            if dest_quality_profiles and len(dest_quality_profiles) > 0:
                dest_quality_profile_id = dest_quality_profiles[0]["id"]

            dest_root_folder = None
            if dest_root_folders and len(dest_root_folders) > 0:
                dest_root_folder = dest_root_folders[0]["path"]

            if not dest_root_folder:
                print(f"Error: No root folders configured in destination instance '{dest_config['url']}'.")
                print(f"Please add at least one root folder in Radarr Settings > Media Management > Root Folders.")
                print(f"Cannot continue sync without a valid root folder path.")
                return False, 0, 0, 0
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching quality profiles or root folders from destination: {e}")
            return False, 0, 0, 0

        for movie in parent_movies:
            tmdb_id = movie.get("tmdbId")
            if not tmdb_id or tmdb_id not in to_add:
                continue
                
            if not self.apply_filters(movie, filters):
                skipped_count += 1
                continue

            try:
                data = {
                    "title": movie.get("title"),
                    "year": movie.get("year"),
                    "tmdbId": tmdb_id,
                    "qualityProfileId": dest_quality_profile_id,
                    "rootFolderPath": dest_root_folder,
                    "monitored": True,
                    "tags": movie.get("tags", []),
                    "addOptions": {
                        "ignoreEpisodesWithFiles": False,
                        "ignoreEpisodesWithoutFiles": False,
                        "monitor": "movieOnly",
                        "searchForMovie": True,
                        "addMethod": "manual"
                    }
                }

                try:
                    response = requests.post(
                        f"{dest_config['url']}/api/v3/movie",
                        headers=headers,
                        json=data,
                        timeout=30
                    )
                    response.raise_for_status()
                    print(f"Added movie '{movie.get('title')}' to Radarr instance")
                    added_count += 1
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 409:
                        error_details = {}
                        try:
                            error_details = e.response.json()
                        except:
                            pass
                            
                        error_message = error_details.get('message', '')
                        if 'constraint failed' in error_message and 'TmdbId' in error_message:
                            # This is a database constraint failure - the movie exists in the database
                            # but isn't returned by the API (might be in a deleted state)
                            print(f"Skipping movie '{movie.get('title')}' - already exists in destination database (TMDB ID: {tmdb_id})")
                            # Don't count this as a failure since it's not missing from the destination
                            continue

                    error_msg = str(e)
                    try:
                        error_details = e.response.json()
                        error_msg += f" - Details: {error_details}"
                    except:
                        pass
                    print(f"Error adding movie '{movie.get('title')}': {error_msg}")
                    print(f"Request data: {data}")
                    success = False
            except requests.exceptions.RequestException as e:
                print(f"Error adding movie '{movie.get('title')}': {e}")
                success = False

        for tmdb_id in to_remove:
            movie = child_movie_map.get(tmdb_id)
            if not movie:
                continue

            if not self.apply_filters(movie, filters):
                continue

            try:
                movie_id = movie.get("id")
                if movie_id is None:
                    print(f"Cannot remove movie '{movie.get('title')}': Missing internal ID")
                    continue
                    
                delete_url = f"{dest_config['url']}/api/v3/movie/{movie_id}"
                response = requests.delete(
                    delete_url,
                    headers=headers,
                    params={"deleteFiles": False},
                    timeout=30
                )
                response.raise_for_status()
                print(f"Removed movie '{movie.get('title')}' from Radarr instance")
                removed_count += 1
            except requests.exceptions.RequestException as e:
                print(f"Error removing movie '{movie.get('title')}': {e}")
                success = False
                
        return success, added_count, removed_count, skipped_count

    def fetch_indexers(self, instance_name: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch indexer configuration from a server instance."""
        instance_config = self.instances.get(instance_name)
        if not instance_config:
            print(f"Error: Instance {instance_name} not found.")
            return None
        
        headers = self._get_instance_headers(instance_config)
        indexer_url = self._get_instance_url(instance_config, "indexer")
        
        result = self._make_api_request(indexer_url, headers=headers)
        if result is None:
            print(f"Failed to fetch indexers from {instance_name}")
            
        return result


    def get_movie_details(self, instance_name: str, radarr_movie_id: int) -> Optional[Dict[str, Any]]:
        """Fetch details for a specific movie from a Radarr instance using its internal ID."""
        instance_config = self.instances.get(instance_name)
        if not instance_config or instance_config['type'] != 'radarr':
            print(f"Error: Radarr instance {instance_name} not found or invalid type.")
            return None
        
        headers = self._get_instance_headers(instance_config)
        movie_url = self._get_instance_url(instance_config, f"movie/{radarr_movie_id}")
        
        result = self._make_api_request(movie_url, headers=headers)
        
        if result is None:
            print(f"Failed to fetch movie details (Radarr ID: {radarr_movie_id}) from {instance_name}")
            
        return result

    def restore_releases_from_history(self, instance_name: str):
        """Attempts to redownload missing media files based on stored release history."""
        print(f"Starting release restore process for instance: {instance_name}")
        instance_config = self.instances.get(instance_name)
        if not instance_config:
            print(f"Error: Instance {instance_name} not found.")
            return

        instance_db_id = self.db_manager.get_or_create_instance_id(instance_name)
        if instance_db_id is None:
            print(f"Error: Could not get database ID for instance {instance_name}.")
            return

        # 1. Fetch required data
        print("Fetching release history from database...")
        history_records = self.db_manager.get_release_history(instance_db_id)
        if not history_records:
            print("No release history found in database for this instance.")
            return

        print("Fetching current indexers from instance...")
        current_indexers = self.fetch_indexers(instance_name)
        if current_indexers is None:
            print("Failed to fetch current indexers. Aborting restore.")
            return

        print("Fetching current download clients from instance...")
        current_clients = self.fetch_download_clients(instance_name)
        if current_clients is None:
            print("Failed to fetch current download clients. Aborting restore.")
            return

        # 2. Build Mappings (Simple name-based for now, might need refinement)
        indexer_map = {idx.get('name'): idx.get('id') for idx in current_indexers if idx.get('name') and idx.get('id')}
        client_map = {client.get('name'): client.get('id') for client in current_clients if client.get('name') and client.get('id')}

        # 3. Process History Records
        restored_count = 0
        skipped_count = 0
        error_count = 0
        total_history = len(history_records)
        print(f"Processing {total_history} history records...")

        headers = {"X-Api-Key": instance_config["api_key"]}

        for i, record in enumerate(history_records):
            print(f"Processing record {i+1}/{total_history}: {record.get('source_title')}", end='\r')
            media_type = record.get('media_type')
            media_item_id = record.get('media_item_id') # This is the Sonarr/Radarr internal ID
            guid = record.get('guid')
            indexer_name = record.get('indexer')
            client_name = record.get('download_client')
            source_title = record.get('source_title')

            if not guid or not indexer_name or not media_type or not media_item_id:
                # print(f"Skipping record {record.get('id')}: Missing crucial data (GUID, indexer, type, or media ID).")
                skipped_count += 1
                continue

            # Check if media item still exists and needs file
            item_details = None
            has_file = True # Assume it has a file unless proven otherwise
            if media_type == 'movie':
                item_details = self.get_movie_details(instance_name, media_item_id)
                if item_details:
                    has_file = item_details.get('hasFile', True)
                else:
                    # Movie doesn't exist in Radarr anymore
                    skipped_count += 1
                    continue
            elif media_type == 'episode':
                item_details = self.get_episode_details(instance_name, media_item_id)
                if item_details:
                    has_file = item_details.get('hasFile', True)
                else:
                    # Episode doesn't exist in Sonarr anymore
                    # print(f"Skipping record {record.get('id')}: Episode ID {media_item_id} not found in Sonarr.")
                    skipped_count += 1
                    continue
            
            if has_file:
                # print(f"Skipping record {record.get('id')}: Media item already has a file.")
                skipped_count += 1
                continue

            # Map indexer and client
            target_indexer_id = indexer_map.get(indexer_name)
            target_client_id = client_map.get(client_name) # Optional, Sonarr/Radarr might pick default

            if not target_indexer_id:
                # print(f"Skipping record {record.get('id')}: Indexer '{indexer_name}' not found or inactive in current config.")
                skipped_count += 1
                continue

            # Construct payload for POST /api/v3/release
            payload = {
                "guid": guid,
                "indexerId": target_indexer_id,
                "title": source_title
                # "downloadClientId": target_client_id, # Often optional
            }

            # Attempt to trigger download
            try:
                response = requests.post(
                    f"{instance_config['url']}/api/v3/release",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                # API returns 200 OK on success, sometimes with the release if immediately processed,
                # or if it was added to queue. We consider 2xx successful.
                print(f"\nSuccessfully triggered redownload for: {source_title}")
                restored_count += 1
            except requests.exceptions.HTTPError as e:
                # Handle specific errors, e.g., 400 Bad Request might mean release not found by GUID
                error_body = ""
                try:
                    error_body = e.response.json()
                except:
                    error_body = e.response.text
                print(f"\nHTTP error triggering download for {source_title} (GUID: {guid}): {e} - {error_body}")
                error_count += 1
            except requests.exceptions.RequestException as e:
                print(f"\nError triggering download for {source_title} (GUID: {guid}): {e}")
                error_count += 1
            
            # Optional: Add a small delay to avoid hammering APIs
            time.sleep(0.5)

        print(f"\nRelease restore process finished for {instance_name}.")
        print(f"Summary: Attempted: {total_history}, Triggered: {restored_count}, Skipped: {skipped_count}, Errors: {error_count}")


    def get_episode_details(self, instance_name: str, episode_id: int) -> Optional[Dict[str, Any]]:
        """Fetch details for a specific episode from a Sonarr instance using its ID."""
        instance_config = self.instances.get(instance_name)
        if not instance_config or instance_config['type'] != 'sonarr':
            print(f"Error: Sonarr instance {instance_name} not found or invalid type.")
            return None

        headers = self._get_instance_headers(instance_config)
        episode_url = self._get_instance_url(instance_config, f"episode/{episode_id}")
        
        result = self._make_api_request(episode_url, headers=headers)
        
        if result is None:
            print(f"Failed to fetch episode details (ID: {episode_id}) from {instance_name}")
            
        return result
            print(f"HTTP error fetching indexers from {instance_name}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching indexers from {instance_name}: {e}")
            return None

    def fetch_download_clients(self, instance_name: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch download client configuration from a server instance."""
        instance_config = self.instances.get(instance_name)
        if not instance_config:
            print(f"Error: Instance {instance_name} not found.")
            return None
        
        headers = self._get_instance_headers(instance_config)
        client_url = self._get_instance_url(instance_config, "downloadclient")
        
        result = self._make_api_request(client_url, headers=headers)
        if result is None:
            print(f"Failed to fetch download clients from {instance_name}")
            
        return result

    def sync_shows_to_sonarr(self, parent_shows: List[Dict[str, Any]], child_shows: List[Dict[str, Any]],
                           dest_config: Dict[str, Any], filters: Dict[str, Any]) -> Tuple[bool, int, int, int]:
        """
        Sync shows to a Sonarr instance with exact matching to parent.
        
        Args:
            parent_shows: List of shows from parent instance
            child_shows: List of shows from child instance
            dest_config: Destination instance configuration
            filters: Filters to apply
            
        Returns:
            Tuple of (success, added_count, removed_count, skipped_count)
        """
        headers = {
            "X-Api-Key": dest_config["api_key"],
            "Content-Type": "application/json"
        }

        success = True
        added_count = 0
        removed_count = 0
        skipped_count = 0

        parent_tvdb_ids = {show.get("tvdbId") for show in parent_shows if show.get("tvdbId")}
        child_tvdb_ids = {show.get("tvdbId") for show in child_shows if show.get("tvdbId")}

        child_show_map = {show.get("tvdbId"): show for show in child_shows if show.get("tvdbId")}

        to_add = parent_tvdb_ids - child_tvdb_ids
        to_remove = child_tvdb_ids - parent_tvdb_ids
        
        print(f"Syncing shows: {len(to_add)} to add, {len(to_remove)} to remove")

        try:
            quality_profiles_response = requests.get(
                f"{dest_config['url']}/api/v3/qualityprofile",
                headers=headers,
                timeout=30
            )
            quality_profiles_response.raise_for_status()
            dest_quality_profiles = quality_profiles_response.json()

            root_folders_response = requests.get(
                f"{dest_config['url']}/api/v3/rootfolder",
                headers=headers,
                timeout=30
            )
            root_folders_response.raise_for_status()
            dest_root_folders = root_folders_response.json()

            dest_quality_profile_id = 1
            if dest_quality_profiles and len(dest_quality_profiles) > 0:
                dest_quality_profile_id = dest_quality_profiles[0]["id"]

            dest_root_folder = None
            if dest_root_folders and len(dest_root_folders) > 0:
                dest_root_folder = dest_root_folders[0]["path"]

            if not dest_root_folder:
                print(f"Error: No root folders configured in destination instance '{dest_config['url']}'.")
                print(f"Please add at least one root folder in Sonarr Settings > Media Management > Root Folders.")
                print(f"Cannot continue sync without a valid root folder path.")
                return False, 0, 0, 0
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching quality profiles or root folders from destination: {e}")
            return False, 0, 0, 0

        for show in parent_shows:
            tvdb_id = show.get("tvdbId")
            if not tvdb_id or tvdb_id not in to_add:
                continue
                
            if not self.apply_filters(show, filters):
                skipped_count += 1
                continue

            try:
                search_response = requests.get(
                    f"{dest_config['url']}/api/v3/series/lookup",
                    headers=headers,
                    params={"term": f"tvdb:{tvdb_id}"},
                    timeout=30
                )
                search_response.raise_for_status()
                search_results = search_response.json()

                if search_results:
                    series_data = search_results[0]

                    data = series_data.copy()

                    data.update({
                        "qualityProfileId": dest_quality_profile_id,
                        "rootFolderPath": dest_root_folder,
                        "seasonFolder": True,
                        "monitored": True,
                        "tags": show.get("tags", []),
                        "addOptions": {
                            "ignoreEpisodesWithFiles": False,
                            "ignoreEpisodesWithoutFiles": False,
                            "monitor": "all",
                            "searchForMissingEpisodes": True,
                            "searchForCutoffUnmetEpisodes": False
                        }
                    })

                    if "id" in data:
                        del data["id"]

                    try:
                        response = requests.post(
                            f"{dest_config['url']}/api/v3/series",
                            headers=headers,
                            json=data,
                            timeout=30
                        )
                        response.raise_for_status()
                        print(f"Added show '{show.get('title')}' to Sonarr instance")
                        added_count += 1
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code == 409:
                            error_details = {}
                            try:
                                error_details = e.response.json()
                            except:
                                pass
                                
                            error_message = error_details.get('message', '')
                            if 'constraint failed' in error_message and 'TvdbId' in error_message:
                                print(f"Skipping show '{show.get('title')}' - already exists in destination database (TVDB ID: {tvdb_id})")
                                continue

                        error_msg = str(e)
                        try:
                            error_details = e.response.json()
                            error_msg += f" - Details: {error_details}"
                        except:
                            pass
                        print(f"Error adding show '{show.get('title')}': {error_msg}")
                        print(f"Request data: {data}")
                        success = False
                else:
                    print(f"Show '{show.get('title')}' not found in Sonarr lookup")
                    success = False
            except requests.exceptions.RequestException as e:
                print(f"Error adding show '{show.get('title')}': {e}")
                success = False

        for tvdb_id in to_remove:
            show = child_show_map.get(tvdb_id)
            if not show:
                continue

            if not self.apply_filters(show, filters):
                continue

            try:
                show_id = show.get("id")
                if show_id is None:
                    print(f"Cannot remove show '{show.get('title')}': Missing internal ID")
                    continue
                    
                delete_url = f"{dest_config['url']}/api/v3/series/{show_id}"
                response = requests.delete(
                    delete_url,
                    headers=headers,
                    params={"deleteFiles": False},
                    timeout=30
                )
                response.raise_for_status()
                print(f"Removed show '{show.get('title')}' from Sonarr instance")
                removed_count += 1
            except requests.exceptions.RequestException as e:
                print(f"Error removing show '{show.get('title')}': {e}")
                success = False

        return success, added_count, removed_count, skipped_count

class CliInterface:
    """
    Command-line interface for the Arrranger application.
    
    Provides an interactive command-line interface for managing media server
    instances, performing backups and syncs, and other maintenance operations.
    Integrates with the MediaServerManager, BackupManager, and SyncManager
    to expose their functionality through a user-friendly menu system.
    
    Handles user input validation, option selection, and presents results
    in a readable format for command-line operation.
    """
    
    def __init__(self):
        """Initialize the CLI interface with required managers."""
        self.manager = MediaServerManager()
        self.backup_manager = BackupManager(self.manager.db_manager, self.manager.api_client)
        self.sync_manager = SyncManager(self.manager.db_manager, self.manager.api_client)
    
    def display_menu(self) -> None:
        """Display the main menu options."""
        print("\nOptions:")
        print("1. Add a new media server instance")
        print("2. Remove a media server instance")
        print("3. Perform manual backup")
        print("4. Perform manual sync")
        print("5. Restore from backup")
        print("6. View configured instances")
        print("7. Restore Releases from History")
        print("8. Exit")
    
    def get_instance_choice(self, prompt: str) -> Optional[str]:
        """
        Get a user selection from available instances.
        
        Args:
            prompt: Message to display when asking for selection
            
        Returns:
            Optional[str]: Selected instance name or None if invalid selection
        """
        if not self.manager.instances:
            print("No instances configured.")
            return None
            
        print("\nAvailable instances:")
        for i, name in enumerate(self.manager.instances.keys(), 1):
            print(f"{i}. {name} ({self.manager.instances[name]['type']})")
            
        try:
            index = int(input(prompt)) - 1
            if 0 <= index < len(self.manager.instances):
                return list(self.manager.instances.keys())[index]
            else:
                print("Invalid instance number.")
                return None
        except ValueError:
            print("Invalid input. Please enter a number.")
            return None
    
    def add_instance(self) -> None:
        """Add a new media server instance with user input."""
        name = input("Enter a name for the instance: ")
        url = input(f"Enter the URL for {name}: ").strip()
        api_key = input(f"Enter the API key for {name}: ").strip()
        instance_type = input("Enter instance type (radarr/sonarr): ").strip().lower()

        backup_config = self._get_backup_config()
        sync_config = self._get_sync_config()
        filters = self._get_filters()

        if self.manager.add_instance(name, url, api_key, instance_type, backup_config, sync_config, filters):
            self.manager.save_instances()
            print(f"Instance {name} added successfully.")
        else:
            print(f"Failed to add instance {name}.")
    
    def _get_backup_config(self) -> Optional[Dict[str, Any]]:
        """Get backup configuration from user input."""
        backup_enabled = input("Enable automatic backup? (y/n): ").lower() == 'y'
        if not backup_enabled:
            return None
            
        cron = input("Enter backup cron expression (e.g. '0 0 * * *' for daily at midnight): ").strip()
        return {
            "enabled": True,
            "schedule": {"type": "cron", "cron": cron}
        }
    
    def _get_sync_config(self) -> Optional[Dict[str, Any]]:
        """Get sync configuration from user input."""
        sync_enabled = input("Configure sync from parent? (y/n): ").lower() == 'y'
        if not sync_enabled:
            return None
            
        parent = input("Enter parent instance name: ").strip()
        cron = input("Enter sync cron expression (e.g. '0 0 * * *' for daily at midnight): ").strip()
        return {
            "parent_instance": parent,
            "schedule": {"type": "cron", "cron": cron}
        }
    
    def _get_filters(self) -> Dict[str, Any]:
        """Get media filters from user input."""
        filters = {}
        if input("Configure filters? (y/n): ").lower() != 'y':
            return filters
            
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
            
        return filters
    
    def remove_instance(self) -> None:
        """Remove a media server instance."""
        name = self.get_instance_choice("Enter the number of the instance to remove: ")
        if name:
            del self.manager.instances[name]
            self.manager.save_instances()
            print(f"Removed instance: {name}")

    def perform_backup(self) -> None:
        """Perform a manual backup of an instance."""
        name = self.get_instance_choice("Enter the number of the instance to backup: ")
        if name:
            instance_config = self.manager.instances[name]
            if self.backup_manager.backup_media(name, instance_config):
                print("Backup completed successfully.")
            else:
                print("Backup failed.")


class CliInterface:
    """
    Command-line interface for the Arrranger application.
    
    This class provides an interactive CLI for managing media server instances,
    performing backups and syncs, and other maintenance operations.
    """
    
    def __init__(self):
        """Initialize the CLI interface with required managers."""
        self.manager = MediaServerManager()
        self.backup_manager = BackupManager(self.manager.db_manager, self.manager.api_client)
        self.sync_manager = SyncManager(self.manager.db_manager, self.manager.api_client)
    
    def display_menu(self) -> None:
        """Display the main menu options."""
        print("\nOptions:")
        print("1. Add a new media server instance")
        print("2. Remove a media server instance")
        print("3. Perform manual backup")
        print("4. Perform manual sync")
        print("5. Restore from backup")
        print("6. View configured instances")
        print("7. Restore Releases from History")
        print("8. Exit")
    
    def get_instance_choice(self, prompt: str) -> Optional[str]:
        """
        Get a user selection from available instances.
        
        Args:
            prompt: Message to display when asking for selection
            
        Returns:
            Optional[str]: Selected instance name or None if invalid selection
        """
        if not self.manager.instances:
            print("No instances configured.")
            return None
            
        print("\nAvailable instances:")
        for i, name in enumerate(self.manager.instances.keys(), 1):
            print(f"{i}. {name} ({self.manager.instances[name]['type']})")
            
        try:
            index = int(input(prompt)) - 1
            if 0 <= index < len(self.manager.instances):
                return list(self.manager.instances.keys())[index]
            else:
                print("Invalid instance number.")
                return None
        except ValueError:
            print("Invalid input. Please enter a number.")
            return None
    
    def add_instance(self) -> None:
        """Add a new media server instance with user input."""
        name = input("Enter a name for the instance: ")
        url = input(f"Enter the URL for {name}: ").strip()
        api_key = input(f"Enter the API key for {name}: ").strip()
        instance_type = input("Enter instance type (radarr/sonarr): ").strip().lower()

        backup_config = self._get_backup_config()
        sync_config = self._get_sync_config()
        filters = self._get_filters()

        if self.manager.add_instance(name, url, api_key, instance_type, backup_config, sync_config, filters):
            self.manager.save_instances()
            print(f"Instance {name} added successfully.")
        else:
            print(f"Failed to add instance {name}.")
    
    def _get_backup_config(self) -> Optional[Dict[str, Any]]:
        """Get backup configuration from user input."""
        backup_enabled = input("Enable automatic backup? (y/n): ").lower() == 'y'
        if not backup_enabled:
            return None
            
        cron = input("Enter backup cron expression (e.g. '0 0 * * *' for daily at midnight): ").strip()
        return {
            "enabled": True,
            "schedule": {"type": "cron", "cron": cron}
        }
    
    def _get_sync_config(self) -> Optional[Dict[str, Any]]:
        """Get sync configuration from user input."""
        sync_enabled = input("Configure sync from parent? (y/n): ").lower() == 'y'
        if not sync_enabled:
            return None
            
        parent = input("Enter parent instance name: ").strip()
        cron = input("Enter sync cron expression (e.g. '0 0 * * *' for daily at midnight): ").strip()
        return {
            "parent_instance": parent,
            "schedule": {"type": "cron", "cron": cron}
        }
    
    def _get_filters(self) -> Dict[str, Any]:
        """Get media filters from user input."""
        filters = {}
        if input("Configure filters? (y/n): ").lower() != 'y':
            return filters
            
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
            
        return filters
    
    def remove_instance(self) -> None:
        """Remove a media server instance."""
        name = self.get_instance_choice("Enter the number of the instance to remove: ")
        if name:
            del self.manager.instances[name]
            self.manager.save_instances()
            print(f"Removed instance: {name}")

    def perform_backup(self) -> None:
        """Perform a manual backup of an instance."""
        name = self.get_instance_choice("Enter the number of the instance to backup: ")
        if name:
            instance_config = self.manager.instances[name]
            if self.backup_manager.backup_media(name, instance_config):
                print("Backup completed successfully.")
            else:
                print("Backup failed.")
    
    def perform_sync(self) -> None:
        """Perform a manual sync between two instances."""
        # Get source instance
        source_name = self.get_instance_choice("Enter the number of the source instance: ")
        if not source_name:
            return
            
        source_type = self.manager.instances[source_name]['type']

        # Find compatible destination instances
        dest_instances = [
            name for name in self.manager.instances.keys()
            if name != source_name and self.manager.instances[name]['type'] == source_type
        ]

        if not dest_instances:
            print(f"No compatible destination instances found for {source_type}.")
            return

        # Display destination options
        print("\nAvailable destination instances:")
        for i, name in enumerate(dest_instances, 1):
            print(f"{i}. {name}")

        # Get destination choice
        try:
            dest_input = int(input(f"Enter the number of the destination instance (1-{len(dest_instances)}): "))
            dest_index = dest_input - 1
            if 0 <= dest_index < len(dest_instances):
                dest_name = dest_instances[dest_index]
                source_config = self.manager.instances[source_name]
                dest_config = self.manager.instances[dest_name]
                
                if self.sync_manager.sync_instances(source_name, dest_name, source_config, dest_config):
                    print("Sync completed successfully.")
                else:
                    print("Sync failed.")
            else:
                print("Invalid destination instance number.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    def restore_from_backup(self) -> None:
        """Restore a media server from a backup."""
        # Get backup instance
        backup_name = self.get_instance_choice("Enter the number of the backup instance: ")
        if not backup_name:
            return
            
        backup_type = self.manager.instances[backup_name]['type']

        # Find compatible destination instances
        dest_instances = [
            name for name in self.manager.instances.keys()
            if self.manager.instances[name]['type'] == backup_type
        ]

        if not dest_instances:
            print(f"No compatible destination instances found for {backup_type}.")
            return

        # Display destination options
        print("\nAvailable destination instances:")
        for i, name in enumerate(dest_instances, 1):
            print(f"{i}. {name}")

        # Get destination choice
        try:
            dest_index = int(input(f"Enter the number of the destination instance (1-{len(dest_instances)}): ")) - 1
            if 0 <= dest_index < len(dest_instances):
                dest_name = dest_instances[dest_index]
                if self.manager.restore_from_backup(backup_name, dest_name):
                    print("Restore completed successfully.")
                else:
                    print("Restore failed.")
            else:
                print("Invalid destination instance number.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    def view_instances(self) -> None:
        """Display all configured instances and their settings."""
        if not self.manager.instances:
            print("No instances configured.")
            return
            
        print("\nConfigured instances:")
        for name, config in self.manager.instances.items():
            print(f"\nName: {name}")
            print(f"Type: {config['type']}")
            print(f"URL: {config['url']}")
            
            # Display backup settings
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

            # Display sync settings
            if config.get('sync', {}).get('parent_instance'):
                print(f"Sync Parent: {config['sync']['parent_instance']}")
                if config['sync'].get('schedule'):
                    sync_schedule = config['sync']['schedule']
                    print(f"Sync Schedule: {sync_schedule['type']}")
                    if sync_schedule['type'] == 'cron':
                        print(f"Sync Cron: {sync_schedule['cron']}")
                    else:
                        print(f"Sync Time: {sync_schedule['time']}")

            # Display filters
            if config.get('filters'):
                print("Filters:")
                for filter_name, filter_value in config['filters'].items():
                    print(f"  {filter_name}: {filter_value}")
    
    def restore_releases(self) -> None:
        """Restore releases from history for an instance."""
        instance_name = self.get_instance_choice(f"Enter instance number to restore releases for: ")
        if instance_name:
            print(f"\nStarting restore process for {instance_name}. This may take a while...")
            self.manager.restore_releases_from_history(instance_name)
    
    def run(self) -> None:
        """Run the CLI interface main loop."""
        while True:
            self.display_menu()
            choice = input("Enter your choice (1-8): ")

            if choice == '1':
                self.add_instance()
            elif choice == '2':
                self.remove_instance()
            elif choice == '3':
                self.perform_backup()
            elif choice == '4':
                self.perform_sync()
            elif choice == '5':
                self.restore_from_backup()
            elif choice == '6':
                self.view_instances()
            elif choice == '7':
                self.restore_releases()
            elif choice == '8':
                break
            else:
                print("Invalid choice. Please enter a number between 1 and 8.")


def main():
    """
    Entry point for the Arrranger CLI application.
    
    Initializes the command-line interface and starts the interactive menu
    for managing media server instances, backups, and synchronization.
    This function serves as the primary entry point when the module is
    executed directly.
    """
    cli = CliInterface()
    cli.run()
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
                        name for name in manager.instances.keys()
                        if name != source_name and manager.instances[name]['type'] == source_type
                    ]

                    if not dest_instances:
                        print(f"No compatible destination instances found for {source_type}.")
                        continue

                    for i, name in enumerate(dest_instances):
                        display_num = i + 1
                        print(f"{display_num}. {name}")

                    dest_input = int(input("Enter the number of the destination instance (1-" + str(len(dest_instances)) + "): "))
                    dest_index = dest_input - 1
                    if 0 <= dest_index < len(dest_instances):
                        dest_name = dest_instances[dest_index]
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
                        name for name in manager.instances.keys()
                        if manager.instances[name]['type'] == backup_type
                    ]

                    if not dest_instances:
                        print(f"No compatible destination instances found for {backup_type}.")
                        continue

                    for i, name in enumerate(dest_instances):
                        display_num = i + 1
                        print(f"{display_num}. {name}")

                    dest_index = int(input("Enter the number of the destination instance: ")) - 1
                    if 0 <= dest_index < len(dest_instances):
                        dest_name = dest_instances[dest_index]
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
            if not manager.instances:
                print("No instances configured.")
                continue
            
            print("\nSelect instance to restore releases for:")
            instance_list = list(manager.instances.keys())
            for i, name in enumerate(instance_list, 1):
                print(f"{i}. {name}")
            
            try:
                idx_input = int(input(f"Enter instance number (1-{len(instance_list)}): "))
                idx = idx_input - 1
                if 0 <= idx < len(instance_list):
                    instance_name = instance_list[idx]
                    print(f"\nStarting restore process for {instance_name}. This may take a while...")
                    manager.restore_releases_from_history(instance_name)
                else:
                    print("Invalid instance number.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == '8': # Adjusted from 7 to 8
            break

        else:
            print("Invalid choice. Please enter a number between 1 and 8.")

if __name__ == "__main__":
    main()
