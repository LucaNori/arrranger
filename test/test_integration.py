"""
Integration tests for the Arrranger application.

Tests the interaction between different components of the application,
focusing on end-to-end functionality.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sqlite3
from datetime import datetime
from src.arrranger_logging import log_backup_operation, log_sync_operation
from src.arrranger_scheduler import MediaServerScheduler, ScheduleManager
from src.arrranger_sync import (
    DatabaseManager,
    ApiClient,
    ConfigManager,
    MediaServerManager
)


class TestBackupIntegration(unittest.TestCase):
    """Test the integration between components for backup operations."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch external dependencies
        self.patches = [
            patch('sqlite3.connect'),
            patch('requests.get'),
            patch('requests.post'),
            patch('builtins.open', mock_open(read_data='{}')),
            patch('os.path.exists', return_value=True),
            patch('src.arrranger_logging.logger')
        ]
        
        # Start all patches
        self.mocks = [p.start() for p in self.patches]
        
        # Extract specific mocks for easier access
        self.mock_connect = self.mocks[0]
        self.mock_get = self.mocks[1]
        self.mock_post = self.mocks[2]
        self.mock_logger = self.mocks[5]
        
        # Configure mock connection and cursor
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_connect.return_value = self.mock_conn
        
        # Configure mock response for API requests
        self.mock_response = MagicMock()
        self.mock_response.json.return_value = {"version": "3.0.0"}
        self.mock_response.raise_for_status = MagicMock()
        self.mock_get.return_value = self.mock_response
        self.mock_post.return_value = self.mock_response
        
        # Create test instances configuration
        self.test_instances = {
            "test-radarr": {
                "type": "radarr",
                "url": "http://test.com",
                "api_key": "test-key",
                "backup": {"enabled": True, "schedule": {"type": "cron", "cron": "0 0 * * *"}}
            }
        }

    def tearDown(self):
        """Tear down test fixtures."""
        # Stop all patches
        for p in self.patches:
            p.stop()

    def test_backup_operation_end_to_end(self):
        """Test a complete backup operation from scheduler to database."""
        # Mock the ConfigManager.load_instances to return test instances
        with patch('src.arrranger_sync.ConfigManager.load_instances') as mock_load:
            mock_load.return_value = self.test_instances
            
            # Mock the ApiClient.make_request to return media data
            media_data = [
                {"tmdbId": 1, "title": "Test Movie", "year": 2020, "qualityProfileId": 1, "rootFolderPath": "/movies", "tags": [1, 2]}
            ]
            
            # Configure the API response for fetch_media
            with patch('src.arrranger_sync.ApiClient.fetch_media') as mock_fetch:
                mock_fetch.return_value = media_data
                
                # Configure the database response for save_media
                self.mock_cursor.fetchall.return_value = []  # No existing media
                self.mock_cursor.fetchone.return_value = [0]  # Previous count
                
                # Create the scheduler
                scheduler = MediaServerScheduler()
                
                # Run the backup
                instance_name = "test-radarr"
                instance_config = self.test_instances[instance_name]
                
                # Mock datetime.now() to return a fixed time
                with patch('src.arrranger_scheduler.datetime') as mock_datetime:
                    now = datetime(2023, 1, 1, 12, 0, 0)
                    mock_datetime.now.return_value = now
                    
                    # Run the backup
                    result = scheduler.run_backup(instance_name, instance_config)
                    
                    # Verify the result
                    self.assertTrue(result)
                    
                    # Verify that the backup was logged
                    log_calls = [
                        call for call in self.mock_logger.info.call_args_list
                        if "BACKUP SUCCESS" in str(call)
                    ]
                    self.assertTrue(len(log_calls) > 0, "Backup success was not logged")
                    
                    # Verify that the last_run was updated
                    self.assertEqual(scheduler.last_run[instance_name], now)


class TestSyncIntegration(unittest.TestCase):
    """Test the integration between components for sync operations."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch external dependencies
        self.patches = [
            patch('sqlite3.connect'),
            patch('requests.get'),
            patch('requests.post'),
            patch('builtins.open', mock_open(read_data='{}')),
            patch('os.path.exists', return_value=True),
            patch('src.arrranger_logging.logger')
        ]
        
        # Start all patches
        self.mocks = [p.start() for p in self.patches]
        
        # Extract specific mocks for easier access
        self.mock_connect = self.mocks[0]
        self.mock_get = self.mocks[1]
        self.mock_post = self.mocks[2]
        self.mock_logger = self.mocks[5]
        
        # Configure mock connection and cursor
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_connect.return_value = self.mock_conn
        
        # Configure mock response for API requests
        self.mock_response = MagicMock()
        self.mock_response.json.return_value = {"version": "3.0.0"}
        self.mock_response.raise_for_status = MagicMock()
        self.mock_get.return_value = self.mock_response
        self.mock_post.return_value = self.mock_response
        
        # Create test instances configuration
        self.test_instances = {
            "parent-radarr": {
                "type": "radarr",
                "url": "http://parent.com",
                "api_key": "parent-key"
            },
            "child-radarr": {
                "type": "radarr",
                "url": "http://child.com",
                "api_key": "child-key",
                "sync": {
                    "parent_instance": "parent-radarr",
                    "schedule": {"type": "cron", "cron": "0 0 * * *"}
                }
            }
        }

    def tearDown(self):
        """Tear down test fixtures."""
        # Stop all patches
        for p in self.patches:
            p.stop()

    def test_sync_operation_end_to_end(self):
        """Test a complete sync operation from scheduler to API."""
        # Mock the ConfigManager.load_instances to return test instances
        with patch('src.arrranger_sync.ConfigManager.load_instances') as mock_load:
            mock_load.return_value = self.test_instances
            
            # Create the scheduler
            scheduler = MediaServerScheduler()
            
            # Mock the manual_sync method to return success
            with patch.object(scheduler.manager, 'manual_sync', return_value=True):
                # Mock datetime.now() to return a fixed time
                with patch('src.arrranger_scheduler.datetime') as mock_datetime:
                    now = datetime(2023, 1, 1, 12, 0, 0)
                    mock_datetime.now.return_value = now
                    
                    # Run the sync
                    result = scheduler.run_sync("child-radarr", "parent-radarr")
                    
                    # Verify the result
                    self.assertTrue(result)
                    
                    # Verify that the sync was logged
                    log_calls = [
                        call for call in self.mock_logger.info.call_args_list
                        if "SYNC SUCCESS" in str(call)
                    ]
                    self.assertTrue(len(log_calls) > 0, "Sync success was not logged")
                    
                    # Verify that the last_run was updated
                    self.assertEqual(scheduler.last_run["sync_child-radarr"], now)


class TestSchedulerIntegration(unittest.TestCase):
    """Test the integration between scheduler components."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch the dependencies
        self.patches = [
            patch('src.arrranger_scheduler.MediaServerManager'),
            patch('src.arrranger_scheduler.BackupManager'),
            patch('src.arrranger_scheduler.schedule'),
            patch('src.arrranger_scheduler.datetime')
        ]
        
        self.mock_media_manager_class = self.patches[0].start()
        self.mock_backup_manager_class = self.patches[1].start()
        self.mock_schedule = self.patches[2].start()
        self.mock_datetime = self.patches[3].start()
        
        # Configure the mocks
        self.mock_media_manager = MagicMock()
        self.mock_backup_manager = MagicMock()
        
        self.mock_media_manager_class.return_value = self.mock_media_manager
        self.mock_backup_manager_class.return_value = self.mock_backup_manager
        
        # Configure datetime.now() to return a fixed time
        now = datetime(2023, 1, 1, 12, 0, 0)
        self.mock_datetime.now.return_value = now
        self.mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        # Configure the media manager to have test instances
        self.test_instances = {
            "test-radarr": {
                "type": "radarr",
                "url": "http://test.com",
                "api_key": "test-key",
                "backup": {
                    "enabled": True,
                    "schedule": {"type": "cron", "cron": "0 0 * * *"}
                }
            }
        }
        self.mock_media_manager.instances = self.test_instances

    def tearDown(self):
        """Tear down test fixtures."""
        for p in self.patches:
            p.stop()

    def test_schedule_backups(self):
        """Test scheduling backups based on configuration."""
        # Create the scheduler
        scheduler = MediaServerScheduler()
        
        # Mock ScheduleManager.get_next_run_time to return a predictable time
        next_run = datetime(2023, 1, 1, 0, 0, 0)  # Midnight
        with patch.object(ScheduleManager, 'get_next_run_time', return_value=next_run):
            # Schedule backups
            scheduler.schedule_backups()
            
            # Verify that schedule.every().day.at() was called
            self.mock_schedule.every.assert_called()
            self.mock_schedule.every().day.at.assert_called_with("00:00")


if __name__ == '__main__':
    unittest.main()