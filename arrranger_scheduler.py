import schedule
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from croniter import croniter
from arrranger_sync import MediaServerManager
from arrranger_logging import log_backup_operation, log_sync_operation

CONFIG_FILE = os.environ.get("CONFIG_FILE", "arrranger_instances.json")

class MediaServerScheduler:
    def __init__(self):
        self.manager = MediaServerManager()
        self.last_run: Dict[str, datetime] = {}

    def should_run_task(self, instance_name: str, schedule: Dict[str, Any]) -> bool:
        """Check if a task should run based on its schedule configuration."""
        if instance_name not in self.last_run:
            return True

        last_run = self.last_run[instance_name]
        now = datetime.now()

        cron = croniter(schedule["cron"], last_run)
        next_run = cron.get_next(datetime)
        return now >= next_run

    def get_next_run_time(self, schedule: Dict[str, Any]) -> datetime:
        """Calculate the next run time based on schedule configuration."""
        now = datetime.now()

        cron = croniter(schedule["cron"], now)
        return cron.get_next(datetime)

    def run_backup(self, instance_name: str, instance_config: Dict[str, Any]):
        """Run backup for a specific instance."""
        try:
            print(f"Running backup for {instance_name}")
            media_data = self.manager.fetch_media_data(instance_name, instance_config)
            if media_data:
                media_type = "movie" if instance_config["type"] == "radarr" else "show"
                current_count, previous_count, added_count, removed_count = self.manager.db_manager.save_media(
                    instance_name, media_type, media_data
                )
                self.last_run[instance_name] = datetime.now()
                
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

                # --- Add Release History Backup Logic ---
                if instance_config.get("backup_release_history", False):
                    print(f"Starting release history backup for {instance_name}...")
                    instance_db_id = self.manager.db_manager.get_or_create_instance_id(instance_name)
                    
                    if instance_db_id is None:
                        print(f"Error: Could not get or create database ID for instance {instance_name}. Skipping history backup.")
                    else:
                        history_added_count = 0
                        history_error_count = 0
                        for media_item in media_data:
                            media_item_internal_id = media_item.get('id') # Sonarr/Radarr internal ID
                            if media_item_internal_id is None:
                                continue 
                            
                            try:
                                # Use the manager instance to call fetch_history_for_media
                                history_data = self.manager.fetch_history_for_media(instance_name, instance_config, media_type, media_item_internal_id)
                                if history_data:
                                    # Use the manager's db_manager instance
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
                # --- End Release History Backup Logic ---

            else:
                log_backup_operation(
                    instance_name=instance_name,
                    success=False,
                    media_type="unknown",
                    error="No media data retrieved"
                )
                print(f"No media data retrieved for {instance_name}")
        except Exception as e:
            error_msg = str(e)
            log_backup_operation(
                instance_name=instance_name,
                success=False,
                media_type="unknown",
                error=error_msg
            )
            print(f"Error during backup for {instance_name}: {error_msg}")

    def run_sync(self, child_name: str, parent_name: str):
        """Run sync from parent to child instance."""
        try:
            print(f"Running sync from {parent_name} to {child_name}")
            success = self.manager.manual_sync(parent_name, child_name)
            if success:
                self.last_run[f"sync_{child_name}"] = datetime.now()
                print(f"Sync completed from {parent_name} to {child_name}")
            else:
                print(f"Sync failed from {parent_name} to {child_name}")
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

    def schedule_backups(self):
        """Schedule backups for instances based on their configuration."""
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

            next_run = self.get_next_run_time(schedule_config)
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

    def run_and_reschedule_backup(self, name: str, config: Dict[str, Any], schedule_config: Dict[str, Any]):
        """Run backup and reschedule the next one at the exact time."""
        self.run_backup(name, config)

        next_run = self.get_next_run_time(schedule_config)

        next_time_str = next_run.strftime("%H:%M")
        schedule.every().day.at(next_time_str).do(
            lambda n=name, c=config, s=schedule_config: self.run_and_reschedule_backup(n, c, s)
        )
    
    def check_and_run_backup(self, name: str, config: Dict[str, Any], schedule_config: Dict[str, Any]):
        """Check if it's time for backup and run if needed."""
        if self.should_run_task(name, schedule_config):
            self.run_backup(name, config)

            next_run = self.get_next_run_time(schedule_config)
            next_time_str = next_run.strftime("%H:%M")

            schedule.clear(tag=f"backup_{name}")

            schedule.every().day.at(next_time_str).tag(f"backup_{name}").do(
                lambda n=name, c=config, s=schedule_config: self.run_and_reschedule_backup(n, c, s)
            )

    def schedule_syncs(self):
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

            next_run = self.get_next_run_time(schedule_config)
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

    def run_and_reschedule_sync(self, child_name: str, parent_name: str, schedule_config: Dict[str, Any]):
        """Run sync and reschedule the next one at the exact time."""
        self.run_sync(child_name, parent_name)

        next_run = self.get_next_run_time(schedule_config)

        next_time_str = next_run.strftime("%H:%M")
        schedule.every().day.at(next_time_str).do(
            lambda c=child_name, p=parent_name, s=schedule_config:
            self.run_and_reschedule_sync(c, p, s)
        )
    
    def check_and_run_sync(self, child_name: str, parent_name: str, schedule_config: Dict[str, Any]):
        """Check if it's time for sync and run if needed."""
        if self.should_run_task(f"sync_{child_name}", schedule_config):
            self.run_sync(child_name, parent_name)

            next_run = self.get_next_run_time(schedule_config)
            next_time_str = next_run.strftime("%H:%M")

            schedule.clear(tag=f"sync_{child_name}")

            schedule.every().day.at(next_time_str).tag(f"sync_{child_name}").do(
                lambda c=child_name, p=parent_name, s=schedule_config:
                self.run_and_reschedule_sync(c, p, s)
            )

    def run(self):
        """Main loop to run the scheduler."""
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

def main():
    scheduler = MediaServerScheduler()
    scheduler.run()

if __name__ == "__main__":
    main()
