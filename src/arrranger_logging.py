"""
Arrranger Logging Module

Provides standardized logging functionality for the Arrranger application.
Implements consistent log formatting for backup and sync operations,
enabling better tracking and troubleshooting of application activities.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# Configure logging with a clean format focused on the message content
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("arrranger")

def _format_timestamp() -> str:
    """
    Generate a formatted timestamp for log messages.
    
    Creates a consistent timestamp format for all log entries to ensure
    logs are easily readable and chronologically sortable.
    
    Returns:
        str: Current timestamp in YYYY-MM-DD HH:MM:SS format
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _calculate_counts(media_count: int, prev_media_count: int,
                     added_count: Optional[int], removed_count: Optional[int]) -> tuple:
    """
    Calculate added and removed counts if not explicitly provided.
    
    Derives the number of added and removed items between backup operations
    when these values aren't explicitly tracked during the operation.
    This ensures consistent reporting even when only before/after counts
    are available.
    
    Args:
        media_count: Current number of media items
        prev_media_count: Previous number of media items
        added_count: Explicitly provided added count (or None)
        removed_count: Explicitly provided removed count (or None)
        
    Returns:
        tuple: Calculated (added_count, removed_count)
    """
    if added_count is None:
        added_count = max(0, media_count - prev_media_count) if prev_media_count is not None else 0
    
    if removed_count is None:
        removed_count = max(0, prev_media_count - media_count) if prev_media_count is not None else 0
        
    return added_count, removed_count

def log_backup_operation(
    instance_name: str,
    success: bool,
    media_type: str,
    media_count: int = 0,
    prev_media_count: int = 0,
    added_count: Optional[int] = None,
    removed_count: Optional[int] = None,
    error: Optional[str] = None
) -> None:
    """
    Log backup operation details in a structured, consistent format.
    
    Creates standardized log entries for backup operations to ensure
    consistent monitoring and troubleshooting. Automatically calculates
    differential counts when not explicitly provided, and formats
    success and failure messages differently for better visibility.
    
    Args:
        instance_name: Name of the instance that was backed up
        success: Whether the backup was successful
        media_type: Type of media (movie/show)
        media_count: Number of media items in the backup
        prev_media_count: Previous count of media items
        added_count: Exact number of items added (if provided)
        removed_count: Exact number of items removed (if provided)
        error: Error message if backup failed
    """
    timestamp = _format_timestamp()
    status = "SUCCESS" if success else "FAILED"
    
    if success:
        added, removed = _calculate_counts(media_count, prev_media_count, added_count, removed_count)
        logger.info(
            f"[{timestamp}] BACKUP {status} | Instance: {instance_name} | "
            f"{media_type.upper()}S: {media_count} | "
            f"Added: {added} | Removed: {removed}"
        )
    else:
        logger.error(
            f"[{timestamp}] BACKUP {status} | Instance: {instance_name} | "
            f"Error: {error or 'Unknown error'}"
        )

def log_sync_operation(
    parent_instance: str,
    child_instance: str,
    success: bool,
    media_type: str,
    added_count: int = 0,
    removed_count: int = 0,
    skipped_count: int = 0,
    error: Optional[str] = None
) -> None:
    """
    Log sync operation details in a structured, consistent format.
    
    Creates standardized log entries for synchronization operations between
    parent and child instances. Tracks the number of items added, removed,
    and skipped during sync to provide clear visibility into sync operations
    and their impact on media libraries.
    
    Args:
        parent_instance: Name of the parent instance
        child_instance: Name of the child instance
        success: Whether the sync was successful
        media_type: Type of media (movie/show)
        added_count: Number of media items added in the sync
        removed_count: Number of media items removed in the sync
        skipped_count: Number of media items skipped due to filters
        error: Error message if sync failed
    """
    timestamp = _format_timestamp()
    status = "SUCCESS" if success else "FAILED"
    
    if success:
        logger.info(
            f"[{timestamp}] SYNC {status} | Parent: {parent_instance} | "
            f"Child: {child_instance} | {media_type.upper()}S | "
            f"Added: {added_count} | Removed: {removed_count} | Skipped: {skipped_count}"
        )
    else:
        logger.error(
            f"[{timestamp}] SYNC {status} | Parent: {parent_instance} | "
            f"Child: {child_instance} | Error: {error or 'Unknown error'}"
        )

def get_media_count(db_manager, instance_name: str, media_type: str) -> Tuple[int, int]:
    """
    Get the current count of media items for an instance from the database.
    
    Queries the database to retrieve the current count of media items for a
    specific instance. Returns the count as a tuple with duplicated values
    to maintain API compatibility with functions that expect both current
    and previous counts.
    
    Args:
        db_manager: Database manager instance with connection methods
        instance_name: Name of the instance to get counts for
        media_type: Type of media ("movie" or "show")
        
    Returns:
        Tuple of (current_count, current_count) - both values are the same
        as this is used for consistency with other functions expecting previous counts
    """
    conn = db_manager.connect()
    cursor = conn.cursor()
    
    table_name = "movies" if media_type == "movie" else "shows"
    instance_field = "radarr_instance" if media_type == "movie" else "sonarr_instance"
    
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {instance_field} = ?", (instance_name,))
        current_count = cursor.fetchone()[0]
        
        return current_count, current_count
    except Exception as e:
        logger.error(f"Error getting media count for {instance_name}: {e}")
        return 0, 0
    finally:
        conn.close()