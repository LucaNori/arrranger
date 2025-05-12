"""
Unit tests for the arrranger_scheduler module.

Tests the scheduling functionality including cron-based scheduling,
backup operations, and sync operations.
"""

import unittest
from unittest.mock import patch, MagicMock, call
import datetime
from src.arrranger_scheduler import (
    ScheduleManager,
    BackupManager,
    MediaServerScheduler
)


class TestScheduleManager(unittest.TestCase):
    """Test cases for the ScheduleManager class."""

    def test_should_run_task_when_never_run(self):
        """Test that a task should run if it has never run before."""
        # When last_run is None (never run), should_run_task should return True
        schedule = {"cron": "0 0 * * *"}  # Daily at midnight
        result = ScheduleManager.should_run_task(None, schedule)
        self.assertTrue(result)

    def test_should_run_task_when_time_passed(self):
        """Test that a task should run if the scheduled time has passed."""
        # Mock datetime.now() to return a fixed time
        now = datetime.datetime(2023, 1, 2, 1, 0, 0)  # Jan 2, 2023, 1:00 AM
        last_run = datetime.datetime(2023, 1, 1, 0, 0, 0)  # Jan 1, 2023, midnight
        schedule = {"cron": "0 0 * * *"}  # Daily at midnight
        
        with patch('src.arrranger_scheduler.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            
            # Create a mock croniter that returns a predictable next run time
            with patch('src.arrranger_scheduler.croniter') as mock_croniter:
                mock_croniter_instance = MagicMock()
                mock_croniter_instance.get_next.return_value = datetime.datetime(2023, 1, 2, 0, 0, 0)
                mock_croniter.return_value = mock_croniter_instance
                
                result = ScheduleManager.should_run_task(last_run, schedule)
                self.assertTrue(result)
                
                # Verify croniter was called with the correct arguments
                mock_croniter.assert_called_once_with(schedule["cron"], last_run)

    def test_should_not_run_task_when_time_not_passed(self):
        """Test that a task should not run if the scheduled time hasn't passed."""
        # Mock datetime.now() to return a fixed time
        now = datetime.datetime(2023, 1, 1, 23, 0, 0)  # Jan 1, 2023, 11:00 PM
        last_run = datetime.datetime(2023, 1, 1, 0, 0, 0)  # Jan 1, 2023, midnight
        schedule = {"cron": "0 0 * * *"}  # Daily at midnight
        
        with patch('src.arrranger_scheduler.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            
            # Create a mock croniter that returns a predictable next run time
            with patch('src.arrranger_scheduler.croniter') as mock_croniter:
                mock_croniter_instance = MagicMock()
                mock_croniter_instance.get_next.return_value = datetime.datetime(2023, 1, 2, 0, 0, 0)
                mock_croniter.return_value = mock_croniter_instance
                
                result = ScheduleManager.should_run_task(last_run, schedule)
                self.assertFalse(result)

    def test_get_next_run_time(self):
        """Test calculating the next run time based on a cron schedule."""
        now = datetime.datetime(2023, 1, 1, 12, 0, 0)  # Jan 1, 2023, noon
        schedule = {"cron": "0 0 * * *"}  # Daily at midnight
        expected_next_run = datetime.datetime(2023, 1, 2, 0, 0, 0)  # Jan 2, 2023, midnight
        
        with patch('src.arrranger_scheduler.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            
            # Create a mock croniter that returns a predictable next run time
            with patch('src.arrranger_scheduler.croniter') as mock_croniter:
                mock_croniter_instance = MagicMock()
                mock_croniter_instance.get_next.return_value = expected_next_run
                mock_croniter.return_value = mock_croniter_instance
                
                result = ScheduleManager.get_next_run_time(schedule)
                self.assertEqual(result, expected_next_run)

    def test_format_next_run_time(self):
        """Test formatting a datetime for use with the schedule library."""
        next_run = datetime.datetime(2023, 1, 1, 14, 30, 0)  # 2:30 PM
        expected_format = "14:30"
        
        result = ScheduleManager.format_next_run_time(next_run)
        self.assertEqual(result, expected_format)


class TestBackupManager(unittest.TestCase):
    """Test cases for the BackupManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_media_manager = MagicMock()
        self.backup_manager = BackupManager(self.mock_media_manager)

    def test_backup_media_success(self):
        """Test successful backup of media data."""
        # Configure mocks
        instance_name = "test-instance"
        instance_config = {"type": "radarr"}
        media_data = [{"id": 1, "title": "Test Movie"}]
        
        self.mock_media_manager.fetch_media_data.return_value = media_data
        self.mock_media_manager.db_manager.save_media.return_value = (10, 9, 1, 0)
        
        # Run the test
        with patch('src.arrranger_scheduler.log_backup_operation') as mock_log:
            result = self.backup_manager.backup_media(instance_name, instance_config)
            
            # Verify the result
            self.assertTrue(result)
            
            # Verify the mock interactions
            self.mock_media_manager.fetch_media_data.assert_called_once_with(instance_name, instance_config)
            self.mock_media_manager.db_manager.save_media.assert_called_once_with(
                instance_name, "movie", media_data
            )
            
            # Verify the log call
            mock_log.assert_called_once_with(
                instance_name=instance_name,
                success=True,
                media_type="movie",
                media_count=10,
                prev_media_count=9,
                added_count=1,
                removed_count=0
            )

    def test_backup_media_no_data(self):
        """Test handling of backup when no media data is retrieved."""
        # Configure mocks
        instance_name = "test-instance"
        instance_config = {"type": "radarr"}
        
        self.mock_media_manager.fetch_media_data.return_value = None
        
        # Run the test
        with patch('src.arrranger_scheduler.log_backup_operation') as mock_log:
            result = self.backup_manager.backup_media(instance_name, instance_config)
            
            # Verify the result
            self.assertFalse(result)
            
            # Verify the log call
            mock_log.assert_called_once_with(
                instance_name=instance_name,
                success=False,
                media_type="unknown",
                error="No media data retrieved"
            )

    def test_backup_media_with_exception(self):
        """Test handling of exceptions during backup."""
        # Configure mocks
        instance_name = "test-instance"
        instance_config = {"type": "radarr"}
        
        self.mock_media_manager.fetch_media_data.side_effect = Exception("Test error")
        
        # Run the test
        with patch('src.arrranger_scheduler.log_backup_operation') as mock_log:
            result = self.backup_manager.backup_media(instance_name, instance_config)
            
            # Verify the result
            self.assertFalse(result)
            
            # Verify the log call
            mock_log.assert_called_once_with(
                instance_name=instance_name,
                success=False,
                media_type="unknown",
                error="Test error"
            )

    def test_backup_with_release_history(self):
        """Test backup with release history enabled."""
        # Configure mocks
        instance_name = "test-instance"
        instance_config = {
            "type": "radarr",
            "backup_release_history": True
        }
        media_data = [{"id": 1, "title": "Test Movie"}]
        
        self.mock_media_manager.fetch_media_data.return_value = media_data
        self.mock_media_manager.db_manager.save_media.return_value = (10, 9, 1, 0)
        
        # Run the test
        with patch('src.arrranger_scheduler.log_backup_operation'):
            with patch.object(self.backup_manager, '_backup_release_history') as mock_backup_history:
                result = self.backup_manager.backup_media(instance_name, instance_config)
                
                # Verify the result
                self.assertTrue(result)
                
                # Verify the backup_release_history was called
                mock_backup_history.assert_called_once_with(
                    instance_name, instance_config, "movie", media_data
                )

    def test_backup_release_history(self):
        """Test the backup of release history."""
        # Configure mocks
        instance_name = "test-instance"
        instance_config = {"type": "radarr"}
        media_type = "movie"
        media_data = [{"id": 1, "title": "Test Movie"}]
        
        self.mock_media_manager.db_manager.get_or_create_instance_id.return_value = 42
        self.mock_media_manager.fetch_history_for_media.return_value = [{"id": 101, "eventType": "grabbed"}]
        self.mock_media_manager.db_manager.save_release_history.return_value = 1
        
        # Run the test
        added, errors = self.backup_manager._backup_release_history(
            instance_name, instance_config, media_type, media_data
        )
        
        # Verify the result
        self.assertEqual(added, 1)
        self.assertEqual(errors, 0)
        
        # Verify the mock interactions
        self.mock_media_manager.db_manager.get_or_create_instance_id.assert_called_once_with(instance_name)
        self.mock_media_manager.fetch_history_for_media.assert_called_once_with(
            instance_name, instance_config, media_type, 1
        )
        self.mock_media_manager.db_manager.save_release_history.assert_called_once_with(
            instance_name, 42, media_type, 1, [{"id": 101, "eventType": "grabbed"}]
        )


class TestMediaServerScheduler(unittest.TestCase):
    """Test cases for the MediaServerScheduler class."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch the MediaServerManager and BackupManager
        self.patcher1 = patch('src.arrranger_scheduler.MediaServerManager')
        self.patcher2 = patch('src.arrranger_scheduler.BackupManager')
        self.patcher3 = patch('src.arrranger_scheduler.ScheduleManager')
        
        self.mock_media_manager_class = self.patcher1.start()
        self.mock_backup_manager_class = self.patcher2.start()
        self.mock_schedule_manager_class = self.patcher3.start()
        
        # Configure the mocks
        self.mock_media_manager = MagicMock()
        self.mock_backup_manager = MagicMock()
        self.mock_schedule_manager = MagicMock()
        
        self.mock_media_manager_class.return_value = self.mock_media_manager
        self.mock_backup_manager_class.return_value = self.mock_backup_manager
        self.mock_schedule_manager_class.return_value = self.mock_schedule_manager
        
        # Create the scheduler
        self.scheduler = MediaServerScheduler()

    def tearDown(self):
        """Tear down test fixtures."""
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()

    def test_run_backup_success(self):
        """Test running a backup successfully."""
        # Configure mocks
        instance_name = "test-instance"
        instance_config = {"type": "radarr"}
        self.mock_backup_manager.backup_media.return_value = True
        
        # Run the test
        with patch('src.arrranger_scheduler.datetime') as mock_datetime:
            now = datetime.datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = now
            
            result = self.scheduler.run_backup(instance_name, instance_config)
            
            # Verify the result
            self.assertTrue(result)
            
            # Verify the mock interactions
            self.mock_backup_manager.backup_media.assert_called_once_with(instance_name, instance_config)
            
            # Verify that last_run was updated
            self.assertEqual(self.scheduler.last_run[instance_name], now)

    def test_run_backup_failure(self):
        """Test handling of backup failure."""
        # Configure mocks
        instance_name = "test-instance"
        instance_config = {"type": "radarr"}
        self.mock_backup_manager.backup_media.return_value = False
        
        # Run the test
        result = self.scheduler.run_backup(instance_name, instance_config)
        
        # Verify the result
        self.assertFalse(result)
        
        # Verify the mock interactions
        self.mock_backup_manager.backup_media.assert_called_once_with(instance_name, instance_config)
        
        # Verify that last_run was not updated
        self.assertNotIn(instance_name, self.scheduler.last_run)

    def test_run_sync_success(self):
        """Test running a sync successfully."""
        # Configure mocks
        child_name = "child-instance"
        parent_name = "parent-instance"
        self.mock_media_manager.manual_sync.return_value = True
        
        # Run the test
        with patch('src.arrranger_scheduler.datetime') as mock_datetime:
            now = datetime.datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = now
            
            result = self.scheduler.run_sync(child_name, parent_name)
            
            # Verify the result
            self.assertTrue(result)
            
            # Verify the mock interactions
            self.mock_media_manager.manual_sync.assert_called_once_with(parent_name, child_name)
            
            # Verify that last_run was updated
            self.assertEqual(self.scheduler.last_run[f"sync_{child_name}"], now)

    def test_run_sync_failure(self):
        """Test handling of sync failure."""
        # Configure mocks
        child_name = "child-instance"
        parent_name = "parent-instance"
        self.mock_media_manager.manual_sync.return_value = False
        
        # Run the test
        result = self.scheduler.run_sync(child_name, parent_name)
        
        # Verify the result
        self.assertFalse(result)
        
        # Verify the mock interactions
        self.mock_media_manager.manual_sync.assert_called_once_with(parent_name, child_name)
        
        # Verify that last_run was not updated
        self.assertNotIn(f"sync_{child_name}", self.scheduler.last_run)

    def test_run_sync_exception(self):
        """Test handling of exceptions during sync."""
        # Configure mocks
        child_name = "child-instance"
        parent_name = "parent-instance"
        self.mock_media_manager.manual_sync.side_effect = Exception("Test error")
        
        # Run the test
        with patch('src.arrranger_scheduler.log_sync_operation') as mock_log:
            result = self.scheduler.run_sync(child_name, parent_name)
            
            # Verify the result
            self.assertFalse(result)
            
            # Verify the log call
            mock_log.assert_called_once_with(
                parent_instance=parent_name,
                child_instance=child_name,
                success=False,
                media_type="unknown",
                error="Test error"
            )


if __name__ == '__main__':
    unittest.main()