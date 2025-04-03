#!/usr/bin/env python3

import os
import shutil
import logging
import zipfile # Added for zipping
import subprocess # Added for running shell commands
import time # Added for sleep
from datetime import datetime

# --- Configuration ---
# Directory containing the Docker config folders to back up
SOURCE_CONFIG_DIR = "/home/danny/config"
# Mounted directory where backups should be stored (temporary location before zipping)
BACKUP_DEST_DIR = "/mnt/titan/Backups/docker_config/temp"
# Base directory containing the corresponding Docker Compose project folders
DOCKER_REPO_DIR = "/home/danny/docker" # Example: /path/to/docker/compose/projects
# Log file location
LOG_FILE = "/home/danny/logs/docker_config_backup.log"
# Number of backups to keep
MAX_BACKUPS = 7
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

def rotate_backups(backup_dir, max_to_keep):
    """Rotates backups in the specified directory, keeping only the newest max_to_keep."""
    logging.info(f"Checking backup rotation in directory: {backup_dir}")
    try:
        # Find backup files matching the pattern
        backup_files = [
            f for f in os.listdir(backup_dir)
            if os.path.isfile(os.path.join(backup_dir, f)) and
               f.startswith("docker_configs_backup_") and f.endswith(".zip")
        ]

        if len(backup_files) <= max_to_keep:
            logging.info(f"Found {len(backup_files)} backups, which is within the limit of {max_to_keep}. No rotation needed.")
            return

        logging.info(f"Found {len(backup_files)} backups. Need to remove {len(backup_files) - max_to_keep} oldest ones.")

        # Sort files alphabetically (timestamp format ensures chronological order)
        backup_files.sort()

        # Identify files to delete
        files_to_delete = backup_files[:-max_to_keep] # All except the last 'max_to_keep' files

        for filename in files_to_delete:
            filepath = os.path.join(backup_dir, filename)
            try:
                os.remove(filepath)
                logging.info(f"Successfully deleted old backup: {filename}")
            except OSError as e:
                logging.error(f"Failed to delete old backup '{filename}': {e}")

    except FileNotFoundError:
        logging.error(f"Backup directory '{backup_dir}' not found during rotation check.")
    except Exception as e:
        logging.error(f"An error occurred during backup rotation: {e}")


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
            except (shutil.Error, OSError) as e:
                logging.error(f"Initial copy failed for directory '{item_name}': {e}")
                logging.info(f"Attempting Docker stop/retry/start for '{item_name}'...")

                docker_project_path = os.path.join(DOCKER_REPO_DIR, item_name)
                container_stopped = False
                retry_successful = False

                if os.path.isdir(docker_project_path):
                    # --- Stop Container ---
                    logging.info(f"Attempting to stop container in: {docker_project_path}")
                    stop_command = f"cd \"{docker_project_path}\" && docker compose stop"
                    try:
                        stop_result = subprocess.run(stop_command, shell=True, check=True, capture_output=True, text=True)
                        logging.info(f"Successfully stopped container for '{item_name}'. Output:\n{stop_result.stdout}")
                        container_stopped = True
                    except subprocess.CalledProcessError as stop_err:
                        logging.error(f"Failed to stop container for '{item_name}'. Error:\n{stop_err.stderr}")
                    except FileNotFoundError:
                         logging.error(f"docker compose command not found. Is Docker installed and in PATH?")
                    except Exception as stop_ex:
                         logging.error(f"An unexpected error occurred while stopping container for '{item_name}': {stop_ex}")


                    if container_stopped:
                        # --- Wait ---
                        logging.info("Waiting 10 seconds for file locks to release...")
                        time.sleep(10)

                        # --- Retry Copy ---
                        logging.info(f"Retrying copy for '{item_name}'...")
                        try:
                            # Ensure destination doesn't exist from partial first attempt
                            if os.path.exists(dest_item_path):
                                if os.path.isdir(dest_item_path):
                                    shutil.rmtree(dest_item_path)
                                else:
                                    os.remove(dest_item_path)
                            shutil.copytree(source_item_path, dest_item_path, symlinks=True, ignore_dangling_symlinks=True)
                            logging.info(f"Successfully backed up directory '{item_name}' on retry.")
                            copied_count += 1 # Count success here
                            retry_successful = True
                        except (shutil.Error, OSError) as retry_e:
                            logging.error(f"Retry copy failed for directory '{item_name}': {retry_e}")
                            # Log specific file errors if available
                            if isinstance(retry_e, shutil.Error) and hasattr(retry_e, 'args') and len(retry_e.args) > 0 and isinstance(retry_e.args[0], list):
                                for src, dst, error_msg in retry_e.args[0]:
                                    logging.warning(f"  - Failed to copy file on retry: {src} due to: {error_msg}")
                            error_count += 1 # Count error only if retry fails

                    # --- Restart Container (always attempt if stop was attempted) ---
                    logging.info(f"Attempting to restart container in: {docker_project_path}")
                    start_command = f"cd \"{docker_project_path}\" && docker compose up -d"
                    try:
                        start_result = subprocess.run(start_command, shell=True, check=True, capture_output=True, text=True)
                        logging.info(f"Successfully restarted container for '{item_name}'. Output:\n{start_result.stdout}")
                    except subprocess.CalledProcessError as start_err:
                        logging.error(f"Failed to restart container for '{item_name}'. Error:\n{start_err.stderr}")
                    except FileNotFoundError:
                         logging.error(f"docker compose command not found. Is Docker installed and in PATH?")
                    except Exception as start_ex:
                         logging.error(f"An unexpected error occurred while restarting container for '{item_name}': {start_ex}")

                else:
                    logging.warning(f"Docker project directory not found for '{item_name}' at '{docker_project_path}'. Skipping stop/retry/start.")
                    error_count += 1 # Count initial error if we can't attempt retry

        else:
            logging.debug(f"Skipping non-directory item: {item_name}")

    logging.info("--------------------")
    logging.info("Backup process finished.")
    logging.info(f"Directories successfully backed up: {copied_count}")
    logging.info(f"Directories with errors: {error_count}")

    # --- Zipping and Cleanup ---
    if copied_count > 0 or error_count > 0: # Only zip if something was attempted
        logging.info("Attempting to create zip archive...")
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            # Place the zip file in the parent directory of BACKUP_DEST_DIR
            backup_parent_dir = os.path.dirname(BACKUP_DEST_DIR)
            zip_filename_base = f"docker_configs_backup_{timestamp}"
            zip_filepath_base = os.path.join(backup_parent_dir, zip_filename_base)

            logging.info(f"Creating archive: {zip_filepath_base}.zip")
            # shutil.make_archive creates the archive.
            # Parameters: base_name, format, root_dir
            # base_name: path to the file to create, excluding format-specific extension (e.g., '.zip')
            # format: 'zip', 'tar', 'gztar', 'bztar', or 'xztar'
            # root_dir: directory that will be the root of the archive. All paths in the archive will be relative to this.
            archive_path = shutil.make_archive(
                base_name=zip_filepath_base,
                format='zip',
                root_dir=BACKUP_DEST_DIR
            )
            logging.info(f"Successfully created archive: {archive_path}")

            # --- Rotate Backups ---
            try:
                rotate_backups(backup_parent_dir, MAX_BACKUPS)
            except Exception as rotation_e:
                # Log rotation errors but don't stop the script
                logging.error(f"An error occurred during backup rotation: {rotation_e}")

            # Cleanup: Remove the original backup directory after successful zipping
            try:
                logging.info(f"Attempting to remove original backup directory: {BACKUP_DEST_DIR}")
                shutil.rmtree(BACKUP_DEST_DIR)
                logging.info(f"Successfully removed original backup directory: {BACKUP_DEST_DIR}")
            except OSError as e:
                logging.error(f"Failed to remove original backup directory '{BACKUP_DEST_DIR}': {e}")

        except Exception as e:
            logging.error(f"Failed to create or cleanup zip archive: {e}")
    else:
        logging.info("No directories were processed, skipping zip creation.")

    logging.info("--------------------")
    logging.info("Backup script finished.")
    logging.info("--------------------")


if __name__ == "__main__":
    print("Executing backup script...") # Added for debugging linter issues
    backup_configs()
