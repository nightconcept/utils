#!/bin/bash

# Configuration
BACKUP_SOURCE="/mnt/dietpi-backup"
BACKUP_DEST="/mnt/titan/Backups/dietpi"
LOG_FILE="/root/dietpi-network-backup.log"
MAX_BACKUPS=5

# Create timestamp
TIMESTAMP=$(date +%Y-%m-%d)
BACKUP_NAME="dietpi-backup-$TIMESTAMP"
ZIP_FILE="/tmp/$BACKUP_NAME.zip"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Start backup
echo "Starting backup: $BACKUP_NAME"
log "Starting backup: $BACKUP_NAME"

# Check dependencies
check_dependencies() {
    if ! command -v zip >/dev/null 2>&1; then
        echo "zip not found - attempting to install..."
        log "zip not found - attempting to install..."
        if ! sudo apt-get update && sudo apt-get install -y zip; then
            echo "ERROR: Failed to install zip package"
            log "ERROR: Failed to install zip package"
            exit 1
        fi
        echo "Successfully installed zip package"
    fi
}

# Check and install dependencies
echo "Checking dependencies..."
check_dependencies

# Create zip archive
echo "Creating backup archive..."
if ! zip -r "$ZIP_FILE" "$BACKUP_SOURCE" >/dev/null 2>&1; then
    echo "ERROR: Failed to create zip archive"
    log "ERROR: Failed to create zip archive"
    exit 1
fi

# Check if destination is mounted
echo "Verifying backup destination..."
if ! mountpoint -q "$BACKUP_DEST"; then
    echo "ERROR: Backup destination not mounted"
    log "ERROR: Backup destination not mounted"
    rm -f "$ZIP_FILE"
    exit 1
fi

# Transfer zip file
echo "Transferring backup to $BACKUP_DEST..."
if ! mv "$ZIP_FILE" "$BACKUP_DEST/"; then
    echo "ERROR: Failed to move backup to destination"
    log "ERROR: Failed to move backup to destination"
    rm -f "$ZIP_FILE"
    exit 1
fi

# Cleanup old backups
echo "Cleaning up old backups..."
cd "$BACKUP_DEST" || exit 1
BACKUP_COUNT=$(ls -1 dietpi-backup-*.zip 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
    OLDEST=$(ls -t dietpi-backup-*.zip | tail -n 1)
    rm -f "$OLDEST"
    echo "Removed old backup: $OLDEST"
    log "Removed old backup: $OLDEST"
fi

# Complete
echo "Backup completed successfully: $BACKUP_NAME.zip"
log "Backup completed successfully: $BACKUP_NAME.zip"
exit 0
