"""
Unit tests for the arrranger_logging module.

Tests the logging functionality including formatting, counting calculations,
and log message generation.
"""

import unittest
from unittest.mock import patch, MagicMock
import logging
from datetime import datetime
from src.arrranger_logging import (
    _format_timestamp,
    _calculate_counts,
    log_backup_operation,
    log_sync_operation,
    get_media_count
)


class TestArrrangerLogging(unittest.TestCase):
    """Test cases for arrranger_logging module functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Capture log messages
        self.log_capture = []
        self.patcher = patch('src.arrranger_logging.logger')
        self.mock_logger = self.patcher.start()
        
        # Configure mock logger to capture log messages
        def capture_log(message):
            self.log_capture.append(message)
        
        self.mock_logger.info.side_effect = capture_log
        self.mock_logger.error.side_effect = capture_log

    def tearDown(self):
        """Tear down test fixtures."""
        self.patcher.stop()
        self.log_capture = []

    def test_format_timestamp(self):
        """Test that timestamp formatting produces expected format."""
        # Mock datetime.now() to return a fixed datetime for testing
        fixed_datetime = datetime(2023, 1, 1, 12, 0, 0)
        with patch('src.arrranger_logging.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_datetime
            
            # Call the function and check the result
            result = _format_timestamp()
            self.assertEqual(result, "2023-01-01 12:00:00")

    def test_calculate_counts_with_provided_values(self):
        """Test count calculation when values are explicitly provided."""
        # When both added and removed counts are provided
        added, removed = _calculate_counts(100, 90, 15, 5)
        self.assertEqual(added, 15)
        self.assertEqual(removed, 5)

    def test_calculate_counts_without_provided_values(self):
        """Test count calculation when values need to be calculated."""
        # When counts need to be calculated from media counts
        added, removed = _calculate_counts(100, 90, None, None)
        self.assertEqual(added, 10)  # 100 - 90
        self.assertEqual(removed, 0)  # No removal detected
        
        # Test when items are removed
        added, removed = _calculate_counts(90, 100, None, None)
        self.assertEqual(added, 0)   # No addition detected
        self.assertEqual(removed, 10)  # 100 - 90

    def test_calculate_counts_with_none_prev_count(self):
        """Test count calculation when previous count is None."""
        added, removed = _calculate_counts(100, None, None, None)
        self.assertEqual(added, 0)
        self.assertEqual(removed, 0)

    def test_log_backup_operation_success(self):
        """Test logging a successful backup operation."""
        # Mock timestamp to get consistent output
        with patch('src.arrranger_logging._format_timestamp') as mock_timestamp:
            mock_timestamp.return_value = "2023-01-01 12:00:00"
            
            # Call the function
            log_backup_operation(
                instance_name="test-instance",
                success=True,
                media_type="movie",
                media_count=100,
                prev_media_count=90,
                added_count=10,
                removed_count=0
            )
            
            # Check that the logger was called with the expected message
            expected_message = (
                "[2023-01-01 12:00:00] BACKUP SUCCESS | Instance: test-instance | "
                "MOVIES: 100 | Added: 10 | Removed: 0"
            )
            self.mock_logger.info.assert_called_once()
            self.assertEqual(self.log_capture[0], expected_message)

    def test_log_backup_operation_failure(self):
        """Test logging a failed backup operation."""
        # Mock timestamp to get consistent output
        with patch('src.arrranger_logging._format_timestamp') as mock_timestamp:
            mock_timestamp.return_value = "2023-01-01 12:00:00"
            
            # Call the function
            log_backup_operation(
                instance_name="test-instance",
                success=False,
                media_type="movie",
                error="Connection failed"
            )
            
            # Check that the logger was called with the expected message
            expected_message = (
                "[2023-01-01 12:00:00] BACKUP FAILED | Instance: test-instance | "
                "Error: Connection failed"
            )
            self.mock_logger.error.assert_called_once()
            self.assertEqual(self.log_capture[0], expected_message)

    def test_log_sync_operation_success(self):
        """Test logging a successful sync operation."""
        # Mock timestamp to get consistent output
        with patch('src.arrranger_logging._format_timestamp') as mock_timestamp:
            mock_timestamp.return_value = "2023-01-01 12:00:00"
            
            # Call the function
            log_sync_operation(
                parent_instance="parent-instance",
                child_instance="child-instance",
                success=True,
                media_type="show",
                added_count=5,
                removed_count=2,
                skipped_count=1
            )
            
            # Check that the logger was called with the expected message
            expected_message = (
                "[2023-01-01 12:00:00] SYNC SUCCESS | Parent: parent-instance | "
                "Child: child-instance | SHOWS | Added: 5 | Removed: 2 | Skipped: 1"
            )
            self.mock_logger.info.assert_called_once()
            self.assertEqual(self.log_capture[0], expected_message)

    def test_log_sync_operation_failure(self):
        """Test logging a failed sync operation."""
        # Mock timestamp to get consistent output
        with patch('src.arrranger_logging._format_timestamp') as mock_timestamp:
            mock_timestamp.return_value = "2023-01-01 12:00:00"
            
            # Call the function
            log_sync_operation(
                parent_instance="parent-instance",
                child_instance="child-instance",
                success=False,
                media_type="show",
                error="API error"
            )
            
            # Check that the logger was called with the expected message
            expected_message = (
                "[2023-01-01 12:00:00] SYNC FAILED | Parent: parent-instance | "
                "Child: child-instance | Error: API error"
            )
            self.mock_logger.error.assert_called_once()
            self.assertEqual(self.log_capture[0], expected_message)

    def test_get_media_count_success(self):
        """Test getting media count from database."""
        # Create a mock database manager
        mock_db_manager = MagicMock()
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        
        # Configure the mocks
        mock_db_manager.connect.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [42]  # Return a count of 42
        
        # Call the function
        current_count, prev_count = get_media_count(mock_db_manager, "test-instance", "movie")
        
        # Check the results
        self.assertEqual(current_count, 42)
        self.assertEqual(prev_count, 42)
        
        # Verify the SQL query used the correct table and field
        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        self.assertIn("movies", args[0])  # Check that the query uses the movies table
        self.assertIn("radarr_instance", args[0])  # Check that it filters by radarr_instance

    def test_get_media_count_show(self):
        """Test getting show count from database."""
        # Create a mock database manager
        mock_db_manager = MagicMock()
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        
        # Configure the mocks
        mock_db_manager.connect.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [24]  # Return a count of 24
        
        # Call the function
        current_count, prev_count = get_media_count(mock_db_manager, "test-instance", "show")
        
        # Check the results
        self.assertEqual(current_count, 24)
        self.assertEqual(prev_count, 24)
        
        # Verify the SQL query used the correct table and field
        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        self.assertIn("shows", args[0])  # Check that the query uses the shows table
        self.assertIn("sonarr_instance", args[0])  # Check that it filters by sonarr_instance

    def test_get_media_count_error(self):
        """Test handling of database errors when getting media count."""
        # Create a mock database manager that raises an exception
        mock_db_manager = MagicMock()
        mock_connection = MagicMock()
        
        # Configure the mocks to raise an exception
        mock_db_manager.connect.return_value = mock_connection
        mock_connection.cursor.side_effect = Exception("Database error")
        
        # Call the function and check it handles the error gracefully
        current_count, prev_count = get_media_count(mock_db_manager, "test-instance", "movie")
        
        # Should return zeros on error
        self.assertEqual(current_count, 0)
        self.assertEqual(prev_count, 0)
        
        # Verify that the error was logged
        self.mock_logger.error.assert_called_once()


if __name__ == '__main__':
    unittest.main()