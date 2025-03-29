#!/bin/bash

# Configuration
BACKUP_SOURCE="/mnt/dietpi-backup"
BACKUP_DEST="/mnt/titan/Backups/dietpi"
LOG_FILE="/var/log/dietpi-network-backup.log"
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
log "Starting backup: $BACKUP_NAME"

# Create zip archive
if ! zip -r "$ZIP_FILE" "$BACKUP_SOURCE" >/dev/null 2>&1; then
    log "ERROR: Failed to create zip archive"
    exit 1
fi

# Check if destination is mounted
if ! mountpoint -q "$BACKUP_DEST"; then
    log "ERROR: Backup destination not mounted"
    rm -f "$ZIP_FILE"
    exit 1
fi

# Transfer zip file
if ! mv "$ZIP_FILE" "$BACKUP_DEST/"; then
    log "ERROR: Failed to move backup to destination"
    rm -f "$ZIP_FILE"
    exit 1
fi

# Cleanup old backups
cd "$BACKUP_DEST" || exit 1
BACKUP_COUNT=$(ls -1 dietpi-backup-*.zip 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
    OLDEST=$(ls -t dietpi-backup-*.zip | tail -n 1)
    rm -f "$OLDEST"
    log "Removed old backup: $OLDEST"
fi

# Complete
log "Backup completed successfully: $BACKUP_NAME.zip"
exit 0
