import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("arrranger")

def log_backup_operation(
    instance_name: str,
    success: bool,
    media_type: str,
    media_count: int = 0,
    prev_media_count: int = 0,
    added_count: int = None,
    removed_count: int = None,
    error: Optional[str] = None
) -> None:
    """
    Log backup operation details in a single line format.
    
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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "SUCCESS" if success else "FAILED"
    
    if added_count is None:
        added_count = max(0, media_count - prev_media_count) if prev_media_count is not None else 0
    
    if removed_count is None:
        removed_count = max(0, prev_media_count - media_count) if prev_media_count is not None else 0
    
    if success:
        logger.info(
            f"[{timestamp}] BACKUP {status} | Instance: {instance_name} | "
            f"{media_type.upper()}S: {media_count} | "
            f"Added: {added_count} | Removed: {removed_count}"
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
    Log sync operation details in a single line format.
    
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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

def get_backup_counts(instance_name: str, media_type: str, db_manager) -> Tuple[int, int]:
    """
    Get the current count of media items for an instance from the database.
    
    Returns:
        Tuple of (current count, previous count)
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
        logger.error(f"Error getting backup counts: {e}")
        return 0, 0
    finally:
        conn.close()