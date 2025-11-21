# Database Backup & Recovery Guide

This guide explains how to backup and restore your Star4ce database.

## Quick Start

### Create a Backup

```bash
# Basic backup (saves to ./backups directory)
python3 backup_database.py

# Custom backup location
python3 backup_database.py --output-dir /path/to/backups
```

### Restore from Backup

```bash
# Interactive restore (will ask for confirmation)
python3 restore_database.py backups/star4ce_backup_20241121_020000.db

# Non-interactive restore (use with caution!)
python3 restore_database.py backups/star4ce_backup_20241121_020000.db --confirm
```

### List Available Backups

```bash
python3 restore_database.py --list
```

## Automated Backups

### Using Cron (Linux/macOS)

Add to your crontab (`crontab -e`):

```bash
# Daily backup at 2 AM
0 2 * * * cd /path/to/star4ce-backend && python3 backup_database.py >> /var/log/star4ce-backup.log 2>&1

# Weekly backup on Sundays at 3 AM
0 3 * * 0 cd /path/to/star4ce-backend && python3 backup_database.py --output-dir /backups/weekly >> /var/log/star4ce-backup.log 2>&1
```

### Using Systemd Timer (Linux)

Create `/etc/systemd/system/star4ce-backup.service`:

```ini
[Unit]
Description=Star4ce Database Backup
After=network.target

[Service]
Type=oneshot
User=your-user
WorkingDirectory=/path/to/star4ce-backend
ExecStart=/usr/bin/python3 backup_database.py
Environment="DATABASE_URL=your-database-url"
Environment="BACKUP_DIR=/backups/daily"
```

Create `/etc/systemd/system/star4ce-backup.timer`:

```ini
[Unit]
Description=Daily Star4ce Database Backup
Requires=star4ce-backup.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl enable star4ce-backup.timer
sudo systemctl start star4ce-backup.timer
```

### Using Render Cron Jobs

If deploying on Render, add a Cron Job:

1. Go to your Render dashboard
2. Create a new "Cron Job"
3. Set schedule: `0 2 * * *` (daily at 2 AM)
4. Command: `cd /opt/render/project/src && python3 backup_database.py`
5. Add environment variables:
   - `DATABASE_URL` (automatically available)
   - `BACKUP_DIR=/opt/render/backups`

## Backup Retention

By default, backups older than 30 days are automatically deleted. Configure with:

```bash
export BACKUP_RETENTION_DAYS=60  # Keep backups for 60 days
python3 backup_database.py
```

## Recovery Plan

### Scenario 1: Accidental Data Loss

1. **Stop the application** to prevent new writes
2. **Identify the backup** to restore:
   ```bash
   python3 restore_database.py --list
   ```
3. **Restore from backup**:
   ```bash
   python3 restore_database.py backups/star4ce_backup_YYYYMMDD_HHMMSS.db
   ```
4. **Verify the restore** by checking data
5. **Restart the application**

### Scenario 2: Database Corruption

1. **Stop the application**
2. **Try to backup current state** (may fail, but worth trying)
3. **Restore from most recent backup**
4. **If restore fails**, try older backups
5. **Contact support** if all backups fail

### Scenario 3: Production Disaster Recovery

1. **Set up new server/environment**
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Copy backup file** to new server
4. **Set environment variables** (DATABASE_URL, etc.)
5. **Restore database**:
   ```bash
   python3 restore_database.py backup_file.db --confirm
   ```
6. **Run migrations** if needed:
   ```bash
   python3 migrate_subscription_columns.py
   ```
7. **Start application** and verify

## Backup Storage Recommendations

### Local Development
- Store backups in `./backups` directory
- Keep last 7-14 days of backups
- Manually archive important backups

### Production (Render/Cloud)
- Use **external storage** (S3, Google Cloud Storage, etc.)
- **Never store backups on the same server** as your database
- Keep backups for **at least 90 days**
- Test restore process **monthly**

### Recommended: Cloud Storage Integration

For production, modify `backup_database.py` to upload to S3:

```python
import boto3

def upload_to_s3(backup_path: str, bucket: str):
    s3 = boto3.client('s3')
    key = f"backups/{os.path.basename(backup_path)}"
    s3.upload_file(backup_path, bucket, key)
    print(f"✓ Uploaded to S3: s3://{bucket}/{key}")
```

## Monitoring

### Check Backup Status

```bash
# View backup log
tail -f /var/log/star4ce-backup.log

# Check backup directory size
du -sh backups/

# Count backup files
ls -1 backups/ | wc -l
```

### Alert on Backup Failures

Add email notification to `backup_database.py`:

```python
def send_backup_alert(success: bool, message: str):
    # Use your existing email sending function
    send_email(
        to=os.getenv("ADMIN_EMAIL"),
        subject=f"Backup {'Success' if success else 'Failed'}",
        body=message
    )
```

## Best Practices

1. **Test your backups regularly** - Restore to a test environment monthly
2. **Store backups off-site** - Use cloud storage for production
3. **Document your recovery process** - Keep this guide updated
4. **Monitor backup success** - Set up alerts for failures
5. **Version your backups** - Include timestamps in filenames
6. **Encrypt sensitive backups** - Especially for production data
7. **Keep multiple backup copies** - Follow 3-2-1 rule (3 copies, 2 media types, 1 off-site)

## Troubleshooting

### Backup fails with "Permission denied"
- Check file permissions on backup directory
- Ensure script has write access

### PostgreSQL backup fails
- Install PostgreSQL client tools: `apt-get install postgresql-client` (Linux) or `brew install postgresql` (macOS)
- Verify DATABASE_URL is correct

### SQLite backup is empty
- Check if database file exists and has data
- Verify file path in DATABASE_URL

### Restore overwrites wrong database
- Always verify DATABASE_URL before restoring
- Use `--list` to confirm backup file before restoring

