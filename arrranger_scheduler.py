import schedule
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from croniter import croniter
from arrranger_sync import MediaServerManager

# Use environment variables if available, otherwise use defaults
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

        schedule_type = schedule["type"]
        if schedule_type == "cron":
            cron = croniter(schedule["cron"], last_run)
            next_run = cron.get_next(datetime)
            return now >= next_run
        elif schedule_type == "daily":
            return (now - last_run) >= timedelta(days=1)
        elif schedule_type == "weekly":
            return (now - last_run) >= timedelta(weeks=1)
        elif schedule_type == "monthly":
            return (now - last_run) >= timedelta(days=30)
        return False

    def get_next_run_time(self, schedule: Dict[str, Any]) -> datetime:
        """Calculate the next run time based on schedule configuration."""
        now = datetime.now()
        schedule_type = schedule["type"]

        if schedule_type == "cron":
            cron = croniter(schedule["cron"], now)
            return cron.get_next(datetime)
        else:
            time_parts = schedule["time"].split(":")
            next_run = now.replace(hour=int(time_parts[0]), minute=int(time_parts[1]), second=0, microsecond=0)
            
            if next_run <= now:
                if schedule_type == "daily":
                    next_run += timedelta(days=1)
                elif schedule_type == "weekly":
                    next_run += timedelta(days=7)
                elif schedule_type == "monthly":
                    # Add approximately one month
                    if next_run.month == 12:
                        next_run = next_run.replace(year=next_run.year + 1, month=1)
                    else:
                        next_run = next_run.replace(month=next_run.month + 1)

            return next_run

    def run_backup(self, instance_name: str, instance_config: Dict[str, Any]):
        """Run backup for a specific instance."""
        try:
            print(f"Running backup for {instance_name}")
            media_data = self.manager.fetch_media_data(instance_name, instance_config)
            if media_data:
                media_type = "movie" if instance_config["type"] == "radarr" else "show"
                self.manager.db_manager.save_media(instance_name, media_type, media_data)
                self.last_run[instance_name] = datetime.now()
                print(f"Backup completed for {instance_name}")
            else:
                print(f"No media data retrieved for {instance_name}")
        except Exception as e:
            print(f"Error during backup for {instance_name}: {e}")

    def run_sync(self, child_name: str, parent_name: str):
        """Run sync from parent to child instance."""
        try:
            print(f"Running sync from {parent_name} to {child_name}")
            if self.manager.manual_sync(parent_name, child_name):
                self.last_run[f"sync_{child_name}"] = datetime.now()
                print(f"Sync completed from {parent_name} to {child_name}")
            else:
                print(f"Sync failed from {parent_name} to {child_name}")
        except Exception as e:
            print(f"Error during sync from {parent_name} to {child_name}: {e}")

    def schedule_backups(self):
        """Schedule backups for instances based on their configuration."""
        for name, config in self.manager.instances.items():
            backup_config = config.get("backup", {})
            if not backup_config.get("enabled"):
                continue

            schedule_config = backup_config.get("schedule")
            if not schedule_config:
                continue

            next_run = self.get_next_run_time(schedule_config)
            print(f"Scheduling backup for {name} - Next run at: {next_run}")

            # For cron schedules, calculate the exact time to run
            if schedule_config["type"] == "cron":
                # Convert next run time to HH:MM format for the schedule library
                next_time_str = next_run.strftime("%H:%M")
                
                # Schedule the task at the exact time
                if next_run.date() == datetime.now().date():  # If it's today
                    schedule.every().day.at(next_time_str).do(
                        lambda n=name, c=config, s=schedule_config: self.run_and_reschedule_backup(n, c, s)
                    )
                else:  # If it's tomorrow or later, we'll reschedule when it runs
                    schedule.every().minute.do(
                        lambda n=name, c=config, s=schedule_config: self.check_and_run_backup(n, c, s)
                    )
            else:
                schedule.every().day.at(schedule_config["time"]).do(
                    lambda n=name, c=config, s=schedule_config: self.check_and_run_backup(n, c, s)
                )

    def run_and_reschedule_backup(self, name: str, config: Dict[str, Any], schedule_config: Dict[str, Any]):
        """Run backup and reschedule the next one at the exact time."""
        # Run the backup
        self.run_backup(name, config)
        
        # Calculate the next run time
        next_run = self.get_next_run_time(schedule_config)
        
        # Schedule the next backup at the exact time
        next_time_str = next_run.strftime("%H:%M")
        schedule.every().day.at(next_time_str).do(
            lambda n=name, c=config, s=schedule_config: self.run_and_reschedule_backup(n, c, s)
        )
    
    def check_and_run_backup(self, name: str, config: Dict[str, Any], schedule_config: Dict[str, Any]):
        """Check if it's time for backup and run if needed."""
        if self.should_run_task(name, schedule_config):
            self.run_backup(name, config)
            
            # Re-schedule for the exact next time
            next_run = self.get_next_run_time(schedule_config)
            next_time_str = next_run.strftime("%H:%M")
            
            # Clear previous schedule for this task
            schedule.clear(tag=f"backup_{name}")
            
            # Schedule for the exact time
            schedule.every().day.at(next_time_str).tag(f"backup_{name}").do(
                lambda n=name, c=config, s=schedule_config: self.run_and_reschedule_backup(n, c, s)
            )

    def schedule_syncs(self):
        """Schedule syncs between instances based on parent-child relationships."""
        # Find all instances with parent configurations
        for child_name, child_config in self.manager.instances.items():
            sync_config = child_config.get("sync", {})
            parent_name = sync_config.get("parent_instance")
            if not parent_name or parent_name not in self.manager.instances:
                continue

            schedule_config = sync_config.get("schedule")
            if not schedule_config:
                continue

            next_run = self.get_next_run_time(schedule_config)
            print(f"Scheduling sync from {parent_name} to {child_name} - Next run at: {next_run}")

            # For cron schedules, calculate the exact time to run
            if schedule_config["type"] == "cron":
                # Convert next run time to HH:MM format for the schedule library
                next_time_str = next_run.strftime("%H:%M")
                
                # Schedule the task at the exact time
                if next_run.date() == datetime.now().date():  # If it's today
                    schedule.every().day.at(next_time_str).do(
                        lambda c=child_name, p=parent_name, s=schedule_config:
                        self.run_and_reschedule_sync(c, p, s)
                    )
                else:  # If it's tomorrow or later, we'll reschedule when it runs
                    schedule.every().minute.do(
                        lambda c=child_name, p=parent_name, s=schedule_config:
                        self.check_and_run_sync(c, p, s)
                    )
            else:
                schedule.every().day.at(schedule_config["time"]).do(
                    lambda c=child_name, p=parent_name, s=schedule_config:
                    self.check_and_run_sync(c, p, s)
                )

    def run_and_reschedule_sync(self, child_name: str, parent_name: str, schedule_config: Dict[str, Any]):
        """Run sync and reschedule the next one at the exact time."""
        # Run the sync
        self.run_sync(child_name, parent_name)
        
        # Calculate the next run time
        next_run = self.get_next_run_time(schedule_config)
        
        # Schedule the next sync at the exact time
        next_time_str = next_run.strftime("%H:%M")
        schedule.every().day.at(next_time_str).do(
            lambda c=child_name, p=parent_name, s=schedule_config:
            self.run_and_reschedule_sync(c, p, s)
        )
    
    def check_and_run_sync(self, child_name: str, parent_name: str, schedule_config: Dict[str, Any]):
        """Check if it's time for sync and run if needed."""
        if self.should_run_task(f"sync_{child_name}", schedule_config):
            self.run_sync(child_name, parent_name)
            
            # Re-schedule for the exact next time
            next_run = self.get_next_run_time(schedule_config)
            next_time_str = next_run.strftime("%H:%M")
            
            # Clear previous schedule for this task
            schedule.clear(tag=f"sync_{child_name}")
            
            # Schedule for the exact time
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
