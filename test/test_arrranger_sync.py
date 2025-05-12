"""
Unit tests for the arrranger_sync module.

Tests the core functionality for database operations, API interactions,
and media server management.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import json
import sqlite3
import requests
from src.arrranger_sync import (
    DatabaseManager,
    ApiClient,
    ConfigManager,
    MediaServerManager
)


class TestDatabaseManager(unittest.TestCase):
    """Test cases for the DatabaseManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch sqlite3.connect to avoid actual database operations
        self.patcher = patch('sqlite3.connect')
        self.mock_connect = self.patcher.start()
        
        # Configure mock connection and cursor
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_connect.return_value = self.mock_conn
        
        # Create the database manager
        self.db_manager = DatabaseManager(db_name=":memory:")

    def tearDown(self):
        """Tear down test fixtures."""
        self.patcher.stop()

    def test_init_database(self):
        """Test database initialization creates required tables."""
        # The init_database method is called in __init__, so we just need to verify
        # that the correct CREATE TABLE statements were executed
        
        # Check that cursor.execute was called for each table creation
        execute_calls = self.mock_cursor.execute.call_args_list
        
        # Verify calls for creating tables
        tables = ["instances", "movies", "shows", "ReleaseHistory"]
        for table in tables:
            self.assertTrue(
                any(f"CREATE TABLE IF NOT EXISTS {table}" in str(call) for call in execute_calls),
                f"No CREATE TABLE statement found for {table}"
            )
        
        # Verify calls for creating indexes
        self.assertTrue(
            any("CREATE INDEX IF NOT EXISTS" in str(call) for call in execute_calls),
            "No CREATE INDEX statements found"
        )
        
        # Verify that changes were committed
        self.mock_conn.commit.assert_called_once()
        
        # Verify that connection was closed
        self.mock_conn.close.assert_called_once()

    def test_connect(self):
        """Test that connect method returns a database connection."""
        # Reset the mock to clear the call history from initialization
        self.mock_connect.reset_mock()
        
        # Call the connect method
        connection = self.db_manager.connect()
        
        # Verify that sqlite3.connect was called with the correct database name
        self.mock_connect.assert_called_once_with(":memory:")
        
        # Verify that the connection was returned
        self.assertEqual(connection, self.mock_conn)

    def test_get_media_count(self):
        """Test getting media count for an instance."""
        # Configure the mock to return a count
        self.mock_cursor.fetchone.return_value = [42]
        
        # Call the method for a movie instance
        count = self.db_manager.get_media_count("test-radarr", "movie")
        
        # Verify the result
        self.assertEqual(count, 42)
        
        # Verify the SQL query used the correct table and field
        self.mock_cursor.execute.assert_called_with(
            "SELECT COUNT(*) FROM movies WHERE radarr_instance = ?",
            ("test-radarr",)
        )
        
        # Reset mocks and test for a show instance
        self.mock_cursor.reset_mock()
        self.mock_cursor.fetchone.return_value = [24]
        
        # Call the method for a show instance
        count = self.db_manager.get_media_count("test-sonarr", "show")
        
        # Verify the result
        self.assertEqual(count, 24)
        
        # Verify the SQL query used the correct table and field
        self.mock_cursor.execute.assert_called_with(
            "SELECT COUNT(*) FROM shows WHERE sonarr_instance = ?",
            ("test-sonarr",)
        )

    def test_get_or_create_instance_id_existing(self):
        """Test getting an existing instance ID."""
        # Configure the mock to return an existing ID
        self.mock_cursor.fetchone.return_value = [42]
        
        # Call the method
        instance_id = self.db_manager.get_or_create_instance_id("test-instance")
        
        # Verify the result
        self.assertEqual(instance_id, 42)
        
        # Verify the SQL query
        self.mock_cursor.execute.assert_called_with(
            "SELECT id FROM instances WHERE name = ?",
            ("test-instance",)
        )
        
        # Verify that no insert was performed
        self.assertNotIn("INSERT INTO instances", str(self.mock_cursor.execute.call_args_list))

    def test_get_or_create_instance_id_new(self):
        """Test creating a new instance ID."""
        # Configure the mock to return None for the select, indicating no existing instance
        self.mock_cursor.fetchone.return_value = None
        self.mock_cursor.lastrowid = 42
        
        # Call the method
        instance_id = self.db_manager.get_or_create_instance_id("test-instance")
        
        # Verify the result
        self.assertEqual(instance_id, 42)
        
        # Verify the SQL queries
        calls = self.mock_cursor.execute.call_args_list
        self.assertEqual(len(calls), 2)
        
        # First call should be the SELECT
        self.assertEqual(
            calls[0],
            call("SELECT id FROM instances WHERE name = ?", ("test-instance",))
        )
        
        # Second call should be the INSERT
        self.assertEqual(
            calls[1],
            call("INSERT INTO instances (name) VALUES (?)", ("test-instance",))
        )
        
        # Verify that changes were committed
        self.mock_conn.commit.assert_called_once()


class TestApiClient(unittest.TestCase):
    """Test cases for the ApiClient class."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_client = ApiClient()

    def test_make_request_get_success(self):
        """Test successful GET request."""
        # Mock the requests.get method
        with patch('requests.get') as mock_get:
            # Configure the mock response
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "ok"}
            mock_get.return_value = mock_response
            
            # Call the method
            result = self.api_client.make_request(
                url="http://test.com/api",
                headers={"X-Api-Key": "test-key"},
                method="GET",
                params={"param": "value"}
            )
            
            # Verify the result
            self.assertEqual(result, {"status": "ok"})
            
            # Verify requests.get was called with the correct arguments
            mock_get.assert_called_once_with(
                "http://test.com/api",
                headers={"X-Api-Key": "test-key"},
                params={"param": "value"},
                timeout=self.api_client.timeout_short
            )

    def test_make_request_post_success(self):
        """Test successful POST request."""
        # Mock the requests.post method
        with patch('requests.post') as mock_post:
            # Configure the mock response
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "created"}
            mock_post.return_value = mock_response
            
            # Call the method
            result = self.api_client.make_request(
                url="http://test.com/api",
                headers={"X-Api-Key": "test-key"},
                method="POST",
                json_data={"data": "value"}
            )
            
            # Verify the result
            self.assertEqual(result, {"status": "created"})
            
            # Verify requests.post was called with the correct arguments
            mock_post.assert_called_once_with(
                "http://test.com/api",
                headers={"X-Api-Key": "test-key"},
                params=None,
                json={"data": "value"},
                timeout=self.api_client.timeout_short
            )

    def test_make_request_http_error(self):
        """Test handling of HTTP errors."""
        # Mock the requests.get method to raise an HTTPError
        with patch('requests.get') as mock_get:
            # Configure the mock to raise an HTTPError
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            
            # Call the method with a spy on _handle_http_error
            with patch.object(self.api_client, '_handle_http_error') as mock_handler:
                result = self.api_client.make_request(
                    url="http://test.com/api",
                    headers={"X-Api-Key": "test-key"}
                )
                
                # Verify the result is None
                self.assertIsNone(result)
                
                # Verify _handle_http_error was called
                mock_handler.assert_called_once()

    def test_verify_connection(self):
        """Test verifying connection to a media server."""
        # Mock the make_request method
        with patch.object(self.api_client, 'make_request') as mock_request:
            # Configure the mock to return a status response
            mock_request.return_value = {"version": "3.0.0"}
            
            # Call the method
            result = self.api_client.verify_connection(
                url="http://test.com",
                api_key="test-key"
            )
            
            # Verify the result
            self.assertEqual(result, {"version": "3.0.0"})
            
            # Verify make_request was called with the correct arguments
            mock_request.assert_called_once_with(
                "http://test.com/api/v3/system/status",
                headers={"X-Api-Key": "test-key"},
                timeout=self.api_client.timeout_short
            )


class TestConfigManager(unittest.TestCase):
    """Test cases for the ConfigManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config_manager = ConfigManager(config_file="test_config.json")

    def test_load_instances_file_exists(self):
        """Test loading instances when config file exists."""
        # Mock data
        test_instances = {
            "test-radarr": {"type": "radarr", "url": "http://test.com", "api_key": "test-key"},
            "test-sonarr": {"type": "sonarr", "url": "http://test2.com", "api_key": "test-key2"}
        }
        
        # Mock open to return test data
        mock_file = mock_open(read_data=json.dumps(test_instances))
        
        # Mock os.path.exists to return True
        with patch('os.path.exists', return_value=True):
            # Mock open
            with patch('builtins.open', mock_file):
                # Call the method
                result = self.config_manager.load_instances()
                
                # Verify the result
                self.assertEqual(result, test_instances)
                
                # Verify open was called with the correct file name
                mock_file.assert_called_once_with("test_config.json", "r")

    def test_save_instances(self):
        """Test saving instances to config file."""
        # Mock data
        test_instances = {
            "test-radarr": {"type": "radarr", "url": "http://test.com", "api_key": "test-key"}
        }
        
        # Mock open
        mock_file = mock_open()
        
        # Call the method with mocked open
        with patch('builtins.open', mock_file):
            result = self.config_manager.save_instances(test_instances)
            
            # Verify the result
            self.assertTrue(result)
            
            # Verify open was called with the correct file name and mode
            mock_file.assert_called_once_with("test_config.json", "w")
            
            # Verify json.dump was called with the correct arguments
            handle = mock_file()
            # Get the first call to write and check if it contains the instance name
            write_call = handle.write.call_args_list[0]
            self.assertIn("test-radarr", str(write_call))

    def test_validate_schedule_valid_cron(self):
        """Test validating a valid cron schedule."""
        # Valid cron schedule
        schedule = {"type": "cron", "cron": "0 0 * * *"}
        
        # Mock croniter.is_valid to return True
        with patch('src.arrranger_sync.croniter.is_valid', return_value=True):
            # Call the method
            result = self.config_manager.validate_schedule(schedule)
            
            # Verify the result is True
            self.assertTrue(result)


class TestMediaServerManager(unittest.TestCase):
    """Test cases for the MediaServerManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch the dependencies
        self.patcher1 = patch('src.arrranger_sync.DatabaseManager')
        self.patcher2 = patch('src.arrranger_sync.ApiClient')
        self.patcher3 = patch('src.arrranger_sync.ConfigManager')
        
        self.mock_db_manager_class = self.patcher1.start()
        self.mock_api_client_class = self.patcher2.start()
        self.mock_config_manager_class = self.patcher3.start()
        
        # Configure the mocks
        self.mock_db_manager = MagicMock()
        self.mock_api_client = MagicMock()
        self.mock_config_manager = MagicMock()
        
        self.mock_db_manager_class.return_value = self.mock_db_manager
        self.mock_api_client_class.return_value = self.mock_api_client
        self.mock_config_manager_class.return_value = self.mock_config_manager
        
        # Configure the config manager to return test instances
        self.test_instances = {
            "test-radarr": {"type": "radarr", "url": "http://test.com", "api_key": "test-key"},
            "test-sonarr": {"type": "sonarr", "url": "http://test2.com", "api_key": "test-key2"}
        }
        self.mock_config_manager.load_instances.return_value = self.test_instances
        
        # Create the media server manager
        self.manager = MediaServerManager()

    def tearDown(self):
        """Tear down test fixtures."""
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()

    def test_initialization(self):
        """Test initialization of the MediaServerManager."""
        # Verify that the dependencies were initialized
        self.mock_db_manager_class.assert_called_once()
        self.mock_api_client_class.assert_called_once()
        self.mock_config_manager_class.assert_called_once()
        
        # Verify that instances were loaded
        self.mock_config_manager.load_instances.assert_called_once()
        
        # Verify that the instances were stored
        self.assertEqual(self.manager.instances, self.test_instances)

    def test_save_instances(self):
        """Test saving instances configuration."""
        # Configure the mock to return True
        self.mock_config_manager.save_instances.return_value = True
        
        # Call the method
        result = self.manager.save_instances()
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify the config manager was called with the correct instances
        self.mock_config_manager.save_instances.assert_called_once_with(self.test_instances)


if __name__ == '__main__':
    unittest.main()