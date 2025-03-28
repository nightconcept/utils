#!/usr/bin/env python3

import os
import shutil
import logging
from datetime import datetime

# --- Configuration ---
# Directory containing the Docker config folders to back up
SOURCE_CONFIG_DIR = "/path/to/your/docker/configs"
# Mounted directory where backups should be stored
BACKUP_DEST_DIR = "/mnt/backup/docker_configs"
# Log file location
LOG_FILE = "/var/log/docker_config_backup.log"
# --- End Configuration ---

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def backup_configs():
    """Copies configuration folders from SOURCE_CONFIG_DIR to BACKUP_DEST_DIR."""
    logging.info("Starting Docker config backup...")
    logging.info(f"Source directory: {SOURCE_CONFIG_DIR}")
    logging.info(f"Destination directory: {BACKUP_DEST_DIR}")

    if not os.path.isdir(SOURCE_CONFIG_DIR):
        logging.error(f"Source directory '{SOURCE_CONFIG_DIR}' not found or is not a directory.")
        return

    if not os.path.isdir(BACKUP_DEST_DIR):
        logging.warning(f"Backup destination directory '{BACKUP_DEST_DIR}' not found. Attempting to create it.")
        try:
            os.makedirs(BACKUP_DEST_DIR, exist_ok=True)
            logging.info(f"Successfully created backup destination directory: {BACKUP_DEST_DIR}")
        except OSError as e:
            logging.error(f"Failed to create backup destination directory '{BACKUP_DEST_DIR}': {e}")
            return

    copied_count = 0
    error_count = 0

    for item_name in os.listdir(SOURCE_CONFIG_DIR):
        source_item_path = os.path.join(SOURCE_CONFIG_DIR, item_name)
        dest_item_path = os.path.join(BACKUP_DEST_DIR, item_name)

        if os.path.isdir(source_item_path):
            logging.info(f"Attempting to back up directory: {item_name}")
            try:
                # Remove existing backup directory if it exists, to ensure a fresh copy
                if os.path.exists(dest_item_path):
                     # Use shutil.rmtree for directories
                    if os.path.isdir(dest_item_path):
                        shutil.rmtree(dest_item_path)
                    # Use os.remove for files (though we expect directories here)
                    elif os.path.isfile(dest_item_path):
                         os.remove(dest_item_path)

                # Copy the entire directory tree
                shutil.copytree(source_item_path, dest_item_path, symlinks=True, ignore_dangling_symlinks=True)
                logging.info(f"Successfully backed up directory: {item_name}")
                copied_count += 1
            except shutil.Error as e:
                logging.error(f"Error copying directory '{item_name}': {e}")
                # Log specific file errors if available in the exception
                if hasattr(e, 'args') and len(e.args) > 0 and isinstance(e.args[0], list):
                    for src, dst, error_msg in e.args[0]:
                        logging.warning(f"  - Failed to copy file: {src} due to: {error_msg}")
                        # TODO: Future enhancement:
                        # 1. Identify the Docker container using this file/directory.
                        # 2. Stop the container.
                        # 3. Retry the copy operation for the specific file/directory.
                        # 4. Restart the container.
                error_count += 1
            except OSError as e:
                logging.error(f"OS error copying directory '{item_name}': {e}")
                # This might catch permission errors or other OS-level issues
                # TODO: Add specific handling or container stop/start logic if needed
                error_count += 1
        else:
            logging.debug(f"Skipping non-directory item: {item_name}")

    logging.info("--------------------")
    logging.info("Backup process finished.")
    logging.info(f"Directories successfully backed up: {copied_count}")
    logging.info(f"Directories with errors: {error_count}")
    logging.info("--------------------")


if __name__ == "__main__":
    print("Executing backup script...") # Added for debugging linter issues
    backup_configs()
    