# Quick Start: Database Backup & Restore

## Create a Backup

```bash
cd star4ce-backend
python3 backup_database.py
```

This creates a backup in the `backups/` directory with a timestamp.

## List Available Backups

```bash
python3 restore_database.py --list
```

## Restore from Backup

**⚠️ WARNING: This will overwrite your current database!**

```bash
# List backups first to see the exact filename
python3 restore_database.py --list

# Restore (will ask for confirmation)
python3 restore_database.py backups/star4ce_backup_20251120_165736.db

# Restore without confirmation (use with caution!)
python3 restore_database.py backups/star4ce_backup_20251120_165736.db --confirm
```

## Example Output

```
$ python3 backup_database.py
Starting database backup...
Database: sqlite:///instance/star4ce.db
Output directory: backups
✓ SQLite backup created: backups/star4ce_backup_20251120_165736.db
✓ Cleaned up 0 old backup(s)
✓ Backup completed successfully (0.04 MB)
  Backup location: backups/star4ce_backup_20251120_165736.db

$ python3 restore_database.py --list
Available backups in backups:

  1. star4ce_backup_20251120_165736.db
     Date: 2025-11-20 16:57:36
     Size: 0.04 MB
```

## Automated Daily Backups

Add to your crontab (`crontab -e`):

```bash
# Daily backup at 2 AM
0 2 * * * cd /Users/michaelkhuri/Desktop/star4ce-backend && python3 backup_database.py >> /var/log/star4ce-backup.log 2>&1
```

## Troubleshooting

**"Database file not found"**
- Make sure you're in the `star4ce-backend` directory
- Check that `instance/star4ce.db` exists
- The script will automatically find the database in the `instance/` folder

**"Backup file not found"**
- Use `--list` to see exact backup filenames
- Make sure you're using the full filename from the list
- Check that the `backups/` directory exists

For more details, see `BACKUP_README.md`.

