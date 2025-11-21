# Database Maintenance Guide

Guide for maintaining and backing up your Star4ce database.

---

## Table of Contents

1. [Automatic Backups](#automatic-backups)
2. [Manual Backups](#manual-backups)
3. [Restoring from Backup](#restoring-from-backup)
4. [Database Health Checks](#database-health-checks)
5. [Long-Term Storage](#long-term-storage)
6. [Database Migration](#database-migration)

---

## Automatic Backups

### Render Built-in Backups

Render automatically backs up PostgreSQL databases:

**Free Tier**:
- Daily backups
- Kept for 7 days
- Automatic (no setup needed)

**Paid Tier**:
- More frequent backups (configurable)
- Longer retention periods
- Can export to S3

**How to Access**:
1. Render Dashboard → Your Database
2. Click **"Backups"** tab
3. See list of available backups
4. Click **"Download"** to save locally

**⚠️ IMPORTANT**: Download backups regularly and store in multiple locations!

---

### Automated Backup Script

Use the included `backup_database.py` script for additional backups.

#### Option 1: Render Cron Job (Recommended)

1. **Create Cron Job**:
   - Render Dashboard → **"New +"** → **"Cron Job"**
   - **Name**: `star4ce-daily-backup`
   - **Schedule**: `0 2 * * *` (Daily at 2 AM UTC)
   - **Command**: 
     ```bash
     cd /opt/render/project/src && python3 backup_database.py
     ```
   - **Environment Variables**: Copy all from your backend service

2. **Configure Backup Location**:
   - Add environment variable: `BACKUP_DIR=/opt/render/project/src/backups`
   - Or use default: `backups` folder

3. **Set Retention**:
   - Add environment variable: `BACKUP_RETENTION_DAYS=30`
   - Keeps backups for 30 days (adjust as needed)

**Note**: Render cron jobs run in ephemeral filesystem. For persistent storage, use external storage (S3, etc.).

#### Option 2: External Backup Service

For long-term storage, use external backup service:

1. **Set up S3/Google Drive/Dropbox integration**
2. **Modify backup script** to upload to external storage
3. **Schedule via external cron** (not Render)

---

## Manual Backups

### Using Render Dashboard

1. **Go to Database**:
   - Render Dashboard → Your Database
2. **Click "Backups" tab**
3. **Click "Create Backup"** (if available)
4. **Wait for backup to complete**
5. **Download backup file**

### Using Backup Script

**Local Machine**:
```bash
# Set environment variables
export DATABASE_URL="postgresql://user:pass@host:port/db"
export BACKUP_DIR="./backups"

# Run backup
python3 backup_database.py
```

**From Render Shell** (if available):
```bash
# SSH into Render (if shell access available)
# Or use Render's "Shell" feature
cd /opt/render/project/src
python3 backup_database.py
```

### Using pg_dump Directly

```bash
# Set password
export PGPASSWORD="your-password"

# Create backup
pg_dump -h host -p port -U user -d database -F c -f backup.sql

# Or compressed
pg_dump -h host -p port -U user -d database | gzip > backup.sql.gz
```

---

## Restoring from Backup

### ⚠️ WARNING: Restoring overwrites current data!

**Always backup current data before restoring!**

### Using Restore Script

1. **Download backup file** to your local machine
2. **Set environment variables**:
   ```bash
   export DATABASE_URL="postgresql://user:pass@host:port/db"
   ```
3. **Run restore**:
   ```bash
   python3 restore_database.py /path/to/backup.sql
   ```
4. **Confirm restore** when prompted

### Using pg_restore

```bash
# Set password
export PGPASSWORD="your-password"

# Restore from backup
pg_restore -h host -p port -U user -d database backup.sql

# Or from compressed
gunzip < backup.sql.gz | psql -h host -p port -U user -d database
```

### Using Render Dashboard

1. **Go to Database** → **"Backups"** tab
2. **Click "Restore"** on desired backup
3. **Confirm restore**
4. **Wait for completion**

---

## Database Health Checks

### Weekly Checks

**Check Database Size**:
```sql
SELECT pg_size_pretty(pg_database_size('star4ce'));
```

**Check Table Sizes**:
```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Check Connection Count**:
```sql
SELECT count(*) FROM pg_stat_activity;
```

### Monthly Checks

**Check for Large Tables**:
- Identify tables taking most space
- Consider archiving old data if needed

**Check Index Usage**:
```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans
FROM pg_stat_user_indexes
ORDER BY idx_scan;
```

**Check Slow Queries** (if enabled):
- Review query performance
- Optimize slow queries if needed

### Quarterly Checks

**Vacuum Database**:
```sql
VACUUM ANALYZE;
```

**Check for Orphaned Records**:
- Review foreign key relationships
- Clean up orphaned data if needed

**Review Backup Retention**:
- Ensure backups are being created
- Verify backup storage locations
- Test restore process

---

## Long-Term Storage

### Backup Retention Strategy

**Recommended**:
- **Daily backups**: Keep for 30 days
- **Weekly backups**: Keep for 12 weeks (3 months)
- **Monthly backups**: Keep for 12 months (1 year)
- **Yearly backups**: Keep forever

### Storage Locations

**Primary** (Quick Access):
- Render backups (7-30 days)
- Local backups (30 days)

**Secondary** (Long-term):
- Cloud storage (Google Drive, Dropbox, AWS S3)
- External hard drive
- Another cloud provider (backup of backup)

### Backup Checklist

**Daily**:
- [ ] Verify daily backup was created (automatic)
- [ ] Check backup size is reasonable

**Weekly**:
- [ ] Download weekly backup
- [ ] Store in secondary location
- [ ] Verify backup file is not corrupted

**Monthly**:
- [ ] Download monthly backup
- [ ] Store in multiple locations
- [ ] Test restore process (on test database)
- [ ] Verify all critical data is backed up

**Yearly**:
- [ ] Create yearly archive
- [ ] Store in permanent location
- [ ] Document backup locations
- [ ] Review and update backup strategy

---

## Database Migration

### Adding New Tables

The database automatically creates tables on startup. However, for manual migrations:

1. **Create Migration Script**:
   ```python
   # migrate_add_table.py
   from app import app, db
   
   with app.app_context():
       # Your migration code
       db.create_all()
   ```

2. **Run Migration**:
   ```bash
   python3 migrate_add_table.py
   ```

3. **Verify**:
   - Check tables exist
   - Test application functionality

### Modifying Existing Tables

**⚠️ WARNING**: Modifying existing tables can cause data loss!

1. **Backup First!**:
   ```bash
   python3 backup_database.py
   ```

2. **Create Migration Script**:
   ```python
   # migrate_modify_table.py
   from app import app, db
   from sqlalchemy import text
   
   with app.app_context():
       # Example: Add column
       db.engine.execute(text("ALTER TABLE users ADD COLUMN new_field VARCHAR(255)"))
   ```

3. **Test on Staging First**:
   - Never modify production without testing
   - Test on staging database first

4. **Run Migration**:
   ```bash
   python3 migrate_modify_table.py
   ```

5. **Verify**:
   - Check data integrity
   - Test application functionality

### Using Alembic (Advanced)

For complex migrations, consider using Alembic:

1. **Install Alembic**:
   ```bash
   pip install alembic
   ```

2. **Initialize**:
   ```bash
   alembic init alembic
   ```

3. **Create Migration**:
   ```bash
   alembic revision --autogenerate -m "Add new table"
   ```

4. **Run Migration**:
   ```bash
   alembic upgrade head
   ```

---

## Emergency Procedures

### Database is Corrupted

1. **Stop Application**:
   - Render Dashboard → Your Service → Suspend

2. **Restore from Latest Backup**:
   ```bash
   python3 restore_database.py latest_backup.sql
   ```

3. **Verify Data**:
   - Check critical tables
   - Verify data integrity

4. **Restart Application**:
   - Render Dashboard → Resume service

5. **Monitor**:
   - Check logs for errors
   - Verify application works

### Database is Full

1. **Check Database Size**:
   ```sql
   SELECT pg_size_pretty(pg_database_size('star4ce'));
   ```

2. **Identify Large Tables**:
   ```sql
   -- See table sizes query above
   ```

3. **Archive Old Data**:
   - Export old data to CSV
   - Store in external storage
   - Delete from database (if safe)

4. **Or Upgrade Database**:
   - Render Dashboard → Database → Upgrade Plan
   - Get more storage

### Database Connection Lost

1. **Check Database Status**:
   - Render Dashboard → Database
   - Verify it's running

2. **Resume if Paused**:
   - Free tier databases pause after inactivity
   - Click "Resume"

3. **Check Connection String**:
   - Verify `DATABASE_URL` is correct
   - Use "Internal Database URL" from Render

4. **Restart Backend**:
   - Render Dashboard → Your Service → Manual Deploy

---

## Best Practices

### ✅ DO:

- ✅ Backup before any major changes
- ✅ Test restores regularly
- ✅ Store backups in multiple locations
- ✅ Document backup locations
- ✅ Monitor database size
- ✅ Review backups weekly
- ✅ Keep backups for years (as requested)
- ✅ Encrypt sensitive backups

### ❌ DON'T:

- ❌ Delete backups without verification
- ❌ Store backups only in one location
- ❌ Skip backup verification
- ❌ Modify production without testing
- ❌ Ignore database size warnings
- ❌ Forget to backup before migrations

---

## Backup Verification

### Test Restore Process

**Monthly** (at minimum):

1. **Create Test Database**:
   - Render Dashboard → New PostgreSQL
   - Name: `star4ce-test-restore`

2. **Restore Backup**:
   ```bash
   export DATABASE_URL="postgresql://user:pass@host:port/star4ce-test-restore"
   python3 restore_database.py backup.sql
   ```

3. **Verify Data**:
   - Check table counts
   - Verify sample records
   - Test application with test database

4. **Delete Test Database**:
   - Render Dashboard → Delete test database

### Verify Backup Integrity

**Check Backup File**:
```bash
# For SQL dumps
head -n 20 backup.sql  # Should see SQL statements

# For compressed
gunzip -t backup.sql.gz  # Should not error
```

**Check Backup Size**:
- Should be reasonable (not 0 bytes)
- Should match previous backups (roughly)

---

## Getting Help

If you need help with database maintenance:

1. **Check This Guide**: Review relevant section
2. **Check Render Docs**: https://render.com/docs/databases
3. **Contact Developer**: For complex issues
4. **Render Support**: For Render-specific issues

---

**Last Updated**: 2025-01-20  
**Version**: 1.0

