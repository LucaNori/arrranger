"""
Pytest configuration and shared fixtures.

This module contains pytest fixtures that can be reused across test files,
reducing code duplication and making tests more maintainable.
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
import json
import sqlite3
from datetime import datetime
from src.arrranger_sync import (
    DatabaseManager,
    ApiClient,
    ConfigManager,
    MediaServerManager
)


@pytest.fixture
def mock_sqlite():
    """
    Mock SQLite connections to avoid actual database operations.
    
    Returns:
        tuple: (mock_connect, mock_conn, mock_cursor) for testing database operations
    """
    # Patch sqlite3.connect
    with patch('sqlite3.connect') as mock_connect:
        # Configure mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        yield mock_connect, mock_conn, mock_cursor


@pytest.fixture
def mock_requests():
    """
    Mock requests module to avoid actual HTTP requests.
    
    Returns:
        tuple: (mock_get, mock_post, mock_response) for testing API interactions
    """
    # Patch requests methods
    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        # Configure mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"version": "3.0.0"}
        mock_response.raise_for_status = MagicMock()
        
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        
        yield mock_get, mock_post, mock_response


@pytest.fixture
def mock_file_system():
    """
    Mock file system operations to avoid actual file I/O.
    
    Returns:
        tuple: (mock_open_func, mock_exists) for testing file operations
    """
    # Patch open and os.path.exists
    with patch('builtins.open', mock_open(read_data='{}')) as mock_open_func, \
         patch('os.path.exists', return_value=True) as mock_exists:
        
        yield mock_open_func, mock_exists


@pytest.fixture
def mock_datetime():
    """
    Mock datetime to provide consistent time for tests.
    
    Returns:
        MagicMock: Mocked datetime with now() returning a fixed time
    """
    with patch('datetime.datetime') as mock_dt:
        # Configure datetime.now() to return a fixed time
        fixed_time = datetime(2023, 1, 1, 12, 0, 0)
        mock_dt.now.return_value = fixed_time
        
        # Allow datetime constructor to work normally
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        yield mock_dt


@pytest.fixture
def test_instances():
    """
    Provide test instance configurations for testing.
    
    Returns:
        dict: Sample instance configurations
    """
    return {
        "test-radarr": {
            "type": "radarr",
            "url": "http://test.com",
            "api_key": "test-key",
            "backup": {
                "enabled": True,
                "schedule": {"type": "cron", "cron": "0 0 * * *"}
            }
        },
        "test-sonarr": {
            "type": "sonarr",
            "url": "http://test2.com",
            "api_key": "test-key2",
            "backup": {
                "enabled": True,
                "schedule": {"type": "cron", "cron": "0 0 * * *"}
            }
        },
        "child-radarr": {
            "type": "radarr",
            "url": "http://child.com",
            "api_key": "child-key",
            "sync": {
                "parent_instance": "test-radarr",
                "schedule": {"type": "cron", "cron": "0 0 * * *"}
            }
        }
    }


@pytest.fixture
def sample_movie_data():
    """
    Provide sample movie data for testing.
    
    Returns:
        list: Sample movie data from Radarr API
    """
    return [
        {
            "id": 1,
            "title": "Test Movie 1",
            "year": 2020,
            "tmdbId": 12345,
            "qualityProfileId": 1,
            "rootFolderPath": "/movies",
            "tags": [1, 2]
        },
        {
            "id": 2,
            "title": "Test Movie 2",
            "year": 2021,
            "tmdbId": 67890,
            "qualityProfileId": 1,
            "rootFolderPath": "/movies",
            "tags": [2, 3]
        }
    ]


@pytest.fixture
def sample_show_data():
    """
    Provide sample show data for testing.
    
    Returns:
        list: Sample show data from Sonarr API
    """
    return [
        {
            "id": 1,
            "title": "Test Show 1",
            "year": 2020,
            "tvdbId": 12345,
            "qualityProfileId": 1,
            "rootFolderPath": "/shows",
            "tags": [1, 2]
        },
        {
            "id": 2,
            "title": "Test Show 2",
            "year": 2021,
            "tvdbId": 67890,
            "qualityProfileId": 1,
            "rootFolderPath": "/shows",
            "tags": [2, 3]
        }
    ]


@pytest.fixture
def mock_db_manager(mock_sqlite):
    """
    Create a DatabaseManager with mocked SQLite connections.
    
    Args:
        mock_sqlite: The mock_sqlite fixture
        
    Returns:
        DatabaseManager: A database manager with mocked connections
    """
    _, _, _ = mock_sqlite  # Unpack to ensure the mocks are set up
    return DatabaseManager(db_name=":memory:")


@pytest.fixture
def mock_api_client(mock_requests):
    """
    Create an ApiClient with mocked HTTP requests.
    
    Args:
        mock_requests: The mock_requests fixture
        
    Returns:
        ApiClient: An API client with mocked requests
    """
    _, _, _ = mock_requests  # Unpack to ensure the mocks are set up
    return ApiClient()


@pytest.fixture
def mock_config_manager(mock_file_system, test_instances):
    """
    Create a ConfigManager with mocked file operations.
    
    Args:
        mock_file_system: The mock_file_system fixture
        test_instances: The test_instances fixture
        
    Returns:
        ConfigManager: A config manager with mocked file operations
    """
    _, _ = mock_file_system  # Unpack to ensure the mocks are set up
    
    # Create a ConfigManager
    config_manager = ConfigManager(config_file="test_config.json")
    
    # Mock the load_instances method to return test instances
    config_manager.load_instances = MagicMock(return_value=test_instances)
    
    return config_manager


@pytest.fixture
def mock_media_server_manager(mock_db_manager, mock_api_client, mock_config_manager):
    """
    Create a MediaServerManager with mocked dependencies.
    
    Args:
        mock_db_manager: The mock_db_manager fixture
        mock_api_client: The mock_api_client fixture
        mock_config_manager: The mock_config_manager fixture
        
    Returns:
        MediaServerManager: A media server manager with mocked dependencies
    """
    # Patch the dependencies
    with patch('src.arrranger_sync.DatabaseManager', return_value=mock_db_manager), \
         patch('src.arrranger_sync.ApiClient', return_value=mock_api_client), \
         patch('src.arrranger_sync.ConfigManager', return_value=mock_config_manager):
        
        # Create the media server manager
        manager = MediaServerManager()
        
        yield manager