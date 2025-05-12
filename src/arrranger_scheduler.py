"""
Arrranger Scheduler Module

Provides scheduling functionality for automated backup and synchronization operations.
Implements cron-based scheduling for periodic tasks, manages execution timing,
and coordinates operations between media server instances.
"""

import schedule
import time
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Tuple
from croniter import croniter
from src.arrranger_sync import MediaServerManager
from src.arrranger_logging import log_backup_operation, log_sync_operation

CONFIG_FILE = os.environ.get("CONFIG_FILE", "arrranger_instances.json")

class ScheduleManager:
    """
    Handles scheduling logic for tasks based on cron expressions.
    
    Provides utilities for determining task execution timing using cron expressions.
    Evaluates whether tasks should run based on their last execution time and
    calculates the next scheduled run time, enabling precise time-based automation.
    """
    
    @staticmethod
    def should_run_task(last_run: Optional[datetime], schedule: Dict[str, Any]) -> bool:
        """
        Determine if a task should run based on its schedule and last run time.
        
        Args:
            last_run: When the task was last executed (None if never run)
            schedule: Schedule configuration containing cron expression
            
        Returns:
            bool: True if the task should run now, False otherwise
        """
        if last_run is None:
            return True

        now = datetime.now()
        cron = croniter(schedule["cron"], last_run)
        next_run = cron.get_next(datetime)
        return now >= next_run

    @staticmethod
    def get_next_run_time(schedule: Dict[str, Any]) -> datetime:
        """
        Calculate the next run time based on a cron schedule.
        
        Args:
            schedule: Schedule configuration containing cron expression
            
        Returns:
            datetime: Next scheduled run time
        """
        now = datetime.now()
        cron = croniter(schedule["cron"], now)
        return cron.get_next(datetime)
        
    @staticmethod
    def format_next_run_time(next_run: datetime) -> str:
        """
        Format a run time for use with the schedule library.
        
        Args:
            next_run: The datetime of the next run
            
        Returns:
            str: Time formatted as HH:MM
        """
        return next_run.strftime("%H:%M")


class BackupManager:
    """
    Manages backup operations for media server instances.
    
    Handles the execution of backup operations for media server instances
    on a scheduled basis. Coordinates the process of fetching media data,
    saving it to the database, and optionally backing up release history.
    
    Works in conjunction with the scheduler to ensure backups occur at
    the specified intervals.
    """
    
    def __init__(self, media_manager: MediaServerManager):
        """
        Initialize the backup manager.
        
        Args:
            media_manager: The media server manager to use for operations
        """
        self.manager = media_manager
    
    def backup_media(self, instance_name: str, instance_config: Dict[str, Any]) -> bool:
        """
        Back up media data for a specific instance.
        
        Args:
            instance_name: Name of the instance to back up
            instance_config: Configuration for the instance
            
        Returns:
            bool: True if backup was successful, False otherwise
        """
        try:
            print(f"Running backup for {instance_name}")
            media_data = self.manager.fetch_media_data(instance_name, instance_config)
            if not media_data:
                log_backup_operation(
                    instance_name=instance_name,
                    success=False,
                    media_type="unknown",
                    error="No media data retrieved"
                )
                print(f"No media data retrieved for {instance_name}")
                return False
                
            media_type = "movie" if instance_config["type"] == "radarr" else "show"
            current_count, previous_count, added_count, removed_count = self.manager.db_manager.save_media(
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

            print(f"Backup completed for {instance_name}: {current_count} {media_type}s, {added_count} added, {removed_count} removed")
            
            # Handle release history backup if enabled
            if instance_config.get("backup_release_history", False):
                self._backup_release_history(instance_name, instance_config, media_type, media_data)
                
            return True
            
        except Exception as e:
            error_msg = str(e)
            log_backup_operation(
                instance_name=instance_name,
                success=False,
                media_type="unknown",
                error=error_msg
            )
            print(f"Error during backup for {instance_name}: {error_msg}")
            return False
    
    def _backup_release_history(self, instance_name: str, instance_config: Dict[str, Any],
                               media_type: str, media_data: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Back up release history for media items.
        
        Args:
            instance_name: Name of the instance
            instance_config: Configuration for the instance
            media_type: Type of media (movie or show)
            media_data: List of media items
            
        Returns:
            Tuple[int, int]: Count of (added_records, error_count)
        """
        print(f"Starting release history backup for {instance_name}...")
        instance_db_id = self.manager.db_manager.get_or_create_instance_id(instance_name)
        
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
                history_data = self.manager.fetch_history_for_media(
                    instance_name, instance_config, media_type, media_item_internal_id
                )
                if history_data:
                    added = self.manager.db_manager.save_release_history(
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


class MediaServerScheduler:
    """
    Manages scheduling of backup and sync operations for media server instances.
    
    Coordinates the scheduling and execution of periodic backup and synchronization
    tasks for media server instances. Uses cron expressions to determine execution
    timing and manages the lifecycle of scheduled tasks.
    
    Integrates with the schedule library to handle task execution and provides
    methods for running, checking, and rescheduling tasks as needed.
    """
    
    def __init__(self):
        """Initialize the scheduler with required managers and tracking state."""
        self.manager = MediaServerManager()
        self.backup_manager = BackupManager(self.manager)
        self.schedule_manager = ScheduleManager()
        self.last_run: Dict[str, datetime] = {}

    def run_backup(self, instance_name: str, instance_config: Dict[str, Any]) -> bool:
        """
        Run backup for a specific instance and update last run time.
        
        Args:
            instance_name: Name of the instance to back up
            instance_config: Configuration for the instance
            
        Returns:
            bool: True if backup was successful, False otherwise
        """
        success = self.backup_manager.backup_media(instance_name, instance_config)
        if success:
            self.last_run[instance_name] = datetime.now()
        return success

    def run_sync(self, child_name: str, parent_name: str) -> bool:
        """
        Run sync from parent to child instance and update last run time.
        
        Args:
            child_name: Name of the child instance
            parent_name: Name of the parent instance
            
        Returns:
            bool: True if sync was successful, False otherwise
        """
        try:
            print(f"Running sync from {parent_name} to {child_name}")
            success = self.manager.manual_sync(parent_name, child_name)
            
            if success:
                self.last_run[f"sync_{child_name}"] = datetime.now()
                print(f"Sync completed from {parent_name} to {child_name}")
            else:
                print(f"Sync failed from {parent_name} to {child_name}")
                
            return success
        except Exception as e:
            error_msg = str(e)
            log_sync_operation(
                parent_instance=parent_name,
                child_instance=child_name,
                success=False,
                media_type="unknown",
                error=error_msg
            )
            print(f"Error during sync from {parent_name} to {child_name}: {error_msg}")
            return False

    def _schedule_task(self, task_id: str, next_run: datetime,
                      task_func: Callable, immediate: bool = False) -> None:
        """
        Schedule a task to run at a specific time.
        
        Args:
            task_id: Unique identifier for the task
            next_run: Next scheduled run time
            task_func: Function to call when task runs
            immediate: Whether the task should run immediately if scheduled for today
        """
        next_time_str = self.schedule_manager.format_next_run_time(next_run)
        
        if immediate and next_run.date() == datetime.now().date():
            schedule.every().day.at(next_time_str).tag(task_id).do(task_func)
        else:
            # Check every minute until it's time to run
            schedule.every().minute.tag(f"check_{task_id}").do(
                lambda: self._check_and_run_if_needed(task_id, task_func)
            )
    
    def _check_and_run_if_needed(self, task_id: str, task_func: Callable) -> None:
        """
        Check if a task should run now and execute it if needed.
        
        Args:
            task_id: Unique identifier for the task
            task_func: Function to call when task runs
        """
        # This is a placeholder - actual implementation would check the task's
        # schedule and run the task if needed, then reschedule it
        pass

    def schedule_backups(self) -> None:
        """Schedule backups for all enabled instances based on their configuration."""
        for name, config in self.manager.instances.items():
            backup_config = config.get("backup", {})
            if not backup_config.get("enabled"):
                continue

            schedule_config = backup_config.get("schedule")
            if not schedule_config:
                continue

            if schedule_config.get("type") != "cron" or "cron" not in schedule_config:
                print(f"Warning: Backup for {name} is not using cron scheduling. Only cron is supported.")
                continue

            next_run = self.schedule_manager.get_next_run_time(schedule_config)
            print(f"Scheduling backup for {name} - Next run at: {next_run}")

            next_time_str = next_run.strftime("%H:%M")

            if next_run.date() == datetime.now().date():
                schedule.every().day.at(next_time_str).do(
                    lambda n=name, c=config, s=schedule_config: self.run_and_reschedule_backup(n, c, s)
                )
            else:
                schedule.every().minute.do(
                    lambda n=name, c=config, s=schedule_config: self.check_and_run_backup(n, c, s)
                )

    def run_and_reschedule_backup(self, name: str, config: Dict[str, Any], schedule_config: Dict[str, Any]) -> None:
        """
        Run backup and reschedule the next one at the exact time.
        
        Args:
            name: Name of the instance to back up
            config: Configuration for the instance
            schedule_config: Schedule configuration containing cron expression
        """
        self.run_backup(name, config)

        next_run = self.schedule_manager.get_next_run_time(schedule_config)
        next_time_str = next_run.strftime("%H:%M")
        
        schedule.every().day.at(next_time_str).do(
            lambda n=name, c=config, s=schedule_config: self.run_and_reschedule_backup(n, c, s)
        )
    
    def check_and_run_backup(self, name: str, config: Dict[str, Any], schedule_config: Dict[str, Any]) -> None:
        """
        Check if it's time for backup and run if needed.
        
        Args:
            name: Name of the instance to check
            config: Configuration for the instance
            schedule_config: Schedule configuration containing cron expression
        """
        last_run = self.last_run.get(name)
        if self.schedule_manager.should_run_task(last_run, schedule_config):
            self.run_backup(name, config)

            next_run = self.schedule_manager.get_next_run_time(schedule_config)
            next_time_str = next_run.strftime("%H:%M")

            schedule.clear(tag=f"backup_{name}")

            schedule.every().day.at(next_time_str).tag(f"backup_{name}").do(
                lambda n=name, c=config, s=schedule_config: self.run_and_reschedule_backup(n, c, s)
            )

    def schedule_syncs(self) -> None:
        """Schedule syncs between instances based on parent-child relationships."""
        for child_name, child_config in self.manager.instances.items():
            sync_config = child_config.get("sync", {})
            parent_name = sync_config.get("parent_instance")
            if not parent_name or parent_name not in self.manager.instances:
                continue

            schedule_config = sync_config.get("schedule")
            if not schedule_config:
                continue

            if schedule_config.get("type") != "cron" or "cron" not in schedule_config:
                print(f"Warning: Sync for {child_name} is not using cron scheduling. Only cron is supported.")
                continue

            next_run = self.schedule_manager.get_next_run_time(schedule_config)
            print(f"Scheduling sync from {parent_name} to {child_name} - Next run at: {next_run}")

            next_time_str = next_run.strftime("%H:%M")

            if next_run.date() == datetime.now().date():
                schedule.every().day.at(next_time_str).do(
                    lambda c=child_name, p=parent_name, s=schedule_config:
                    self.run_and_reschedule_sync(c, p, s)
                )
            else:
                schedule.every().minute.do(
                    lambda c=child_name, p=parent_name, s=schedule_config:
                    self.check_and_run_sync(c, p, s)
                )

    def run_and_reschedule_sync(self, child_name: str, parent_name: str, schedule_config: Dict[str, Any]) -> None:
        """
        Run sync and reschedule the next one at the exact time.
        
        Args:
            child_name: Name of the child instance
            parent_name: Name of the parent instance
            schedule_config: Schedule configuration containing cron expression
        """
        self.run_sync(child_name, parent_name)

        next_run = self.schedule_manager.get_next_run_time(schedule_config)
        next_time_str = next_run.strftime("%H:%M")
        
        schedule.every().day.at(next_time_str).do(
            lambda c=child_name, p=parent_name, s=schedule_config:
            self.run_and_reschedule_sync(c, p, s)
        )
    
    def check_and_run_sync(self, child_name: str, parent_name: str, schedule_config: Dict[str, Any]) -> None:
        """
        Check if it's time for sync and run if needed.
        
        Args:
            child_name: Name of the child instance
            parent_name: Name of the parent instance
            schedule_config: Schedule configuration containing cron expression
        """
        task_id = f"sync_{child_name}"
        last_run = self.last_run.get(task_id)
        
        if self.schedule_manager.should_run_task(last_run, schedule_config):
            self.run_sync(child_name, parent_name)

            next_run = self.schedule_manager.get_next_run_time(schedule_config)
            next_time_str = next_run.strftime("%H:%M")

            schedule.clear(tag=task_id)

            schedule.every().day.at(next_time_str).tag(task_id).do(
                lambda c=child_name, p=parent_name, s=schedule_config:
                self.run_and_reschedule_sync(c, p, s)
            )

    def run(self) -> None:
        """Start the scheduler and run the main loop."""
        print("Starting Arrranger Scheduler...")
        
        if not self.manager.instances:
            print("No instances configured. Please run arrranger_sync.py first.")
            return

        self.schedule_backups()
        self.schedule_syncs()

        print("\nScheduled tasks:")
        for job in schedule.get_jobs():
            print(f"- {job}")

        print("\nScheduler running. Press Ctrl+C to exit.")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down scheduler...")


def main() -> None:
    """
    Entry point for the scheduler application.
    
    Initializes the MediaServerScheduler and starts the main scheduling loop.
    This function serves as the primary entry point when the scheduler module
    is executed directly.
    """
    scheduler = MediaServerScheduler()
    scheduler.run()


if __name__ == "__main__":
    main()
