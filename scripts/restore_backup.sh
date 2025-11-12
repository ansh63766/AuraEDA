#!/bin/bash
# Unix/Mac Restore Script
BACKUP_DIR="v2.0_backup"
if [ -d "$BACKUP_DIR" ]; then
    cp -rf "$BACKUP_DIR"/* ./
    echo "Backup successfully restored!"
else
    echo "Backup directory $BACKUP_DIR not found."
fi
