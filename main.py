#!/usr/bin/env python3
"""
Arrranger - Main entry point for the application.

This script serves as the entry point for the Arrranger application,
which manages and synchronizes media servers. It initializes the core
components from the src directory and provides a clean interface for
starting the application.

The application is structured with a modular design, separating concerns
into distinct modules for synchronization, scheduling, and logging to
promote maintainability and testability.
"""

import os
import sys
from src.arrranger_sync import MediaServerManager
from src.arrranger_scheduler import MediaServerScheduler
from src.arrranger_logging import logger

def main():
    """
    Main function that serves as the entry point for the application.
    
    Initializes the MediaServerManager, displays information about configured
    instances, and handles any errors that occur during startup. This function
    returns an exit code that can be used by the system to determine if the
    application executed successfully.
    
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    logger.info("Starting Arrranger application...")
    
    # Example usage of components from src directory
    try:
        # Initialize the media server manager
        manager = MediaServerManager()
        
        # Display the number of configured instances
        instance_count = len(manager.instances)
        logger.info(f"Found {instance_count} configured media server instances")
        
        if instance_count > 0:
            logger.info("Instances:")
            for name, config in manager.instances.items():
                logger.info(f"  - {name} ({config['type']})")
        else:
            logger.info("No instances configured. Please add instances using the sync module.")
            
        # Initialize the scheduler if needed
        # scheduler = MediaServerScheduler()
        # scheduler.run()
        
    except Exception as e:
        logger.error(f"Error initializing Arrranger: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())