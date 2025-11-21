#!/usr/bin/env python3
"""
Database backup script for Star4ce.
Supports both SQLite and PostgreSQL databases.

Usage:
    python3 backup_database.py [--output-dir /path/to/backups]

For automated backups, add to crontab:
    # Daily backup at 2 AM
    0 2 * * * cd /path/to/star4ce-backend && python3 backup_database.py >> /var/log/star4ce-backup.log 2>&1
"""
import os
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def backup_sqlite(db_path: str, output_dir: str) -> str:
    """Backup SQLite database by copying the file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"star4ce_backup_{timestamp}.db"
    backup_path = os.path.join(output_dir, backup_filename)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Copy the database file
    shutil.copy2(db_path, backup_path)
    
    print(f"✓ SQLite backup created: {backup_path}")
    return backup_path

def backup_postgresql(db_url: str, output_dir: str) -> str:
    """Backup PostgreSQL database using pg_dump."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"star4ce_backup_{timestamp}.sql"
    backup_path = os.path.join(output_dir, backup_filename)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Parse database URL
    # Format: postgresql://user:password@host:port/database
    import re
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
    if not match:
        raise ValueError(f"Invalid PostgreSQL URL format: {db_url}")
    
    user, password, host, port, database = match.groups()
    
    # Set PGPASSWORD environment variable for pg_dump
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    
    # Run pg_dump
    cmd = [
        'pg_dump',
        '-h', host,
        '-p', port,
        '-U', user,
        '-d', database,
        '-F', 'c',  # Custom format (compressed)
        '-f', backup_path
    ]
    
    try:
        result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        print(f"✓ PostgreSQL backup created: {backup_path}")
        return backup_path
    except subprocess.CalledProcessError as e:
        print(f"✗ PostgreSQL backup failed: {e.stderr}", file=sys.stderr)
        raise
    except FileNotFoundError:
        print("✗ pg_dump not found. Install PostgreSQL client tools.", file=sys.stderr)
        raise

def cleanup_old_backups(output_dir: str, keep_days: int = 30):
    """Remove backup files older than keep_days."""
    if not os.path.exists(output_dir):
        return
    
    cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
    removed_count = 0
    
    for filename in os.listdir(output_dir):
        filepath = os.path.join(output_dir, filename)
        if os.path.isfile(filepath):
            file_time = os.path.getmtime(filepath)
            if file_time < cutoff_time:
                os.remove(filepath)
                removed_count += 1
                print(f"  Removed old backup: {filename}")
    
    if removed_count > 0:
        print(f"✓ Cleaned up {removed_count} old backup(s)")

def main():
    """Main backup function."""
    # Get output directory from command line or use default
    output_dir = os.getenv("BACKUP_DIR", "backups")
    if len(sys.argv) > 1 and sys.argv[1] == "--output-dir":
        if len(sys.argv) > 2:
            output_dir = sys.argv[2]
        else:
            print("Error: --output-dir requires a path", file=sys.stderr)
            sys.exit(1)
    
    # Get database URL
    db_url = os.getenv("DATABASE_URL", "sqlite:///instance/star4ce.db")
    
    print(f"Starting database backup...")
    print(f"Database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print(f"Output directory: {output_dir}")
    
    try:
        if "sqlite" in db_url.lower():
            # Extract SQLite file path
            db_path = db_url.replace("sqlite:///", "")
            if not os.path.isabs(db_path):
                # Relative path - assume it's relative to the script directory
                script_dir = os.path.dirname(os.path.abspath(__file__))
                db_path = os.path.join(script_dir, db_path)
            
            # Handle instance folder path
            if not os.path.exists(db_path):
                # Try with instance/ prefix
                instance_path = os.path.join(script_dir, "instance", os.path.basename(db_path))
                if os.path.exists(instance_path):
                    db_path = instance_path
                else:
                    # Try just the filename in instance folder
                    instance_path = os.path.join(script_dir, "instance", "star4ce.db")
                    if os.path.exists(instance_path):
                        db_path = instance_path
                    else:
                        print(f"✗ Database file not found: {db_path}", file=sys.stderr)
                        print(f"  Also tried: {instance_path}", file=sys.stderr)
                        print(f"  Current directory: {os.getcwd()}", file=sys.stderr)
                        sys.exit(1)
            
            backup_path = backup_sqlite(db_path, output_dir)
        elif "postgresql" in db_url.lower() or "postgres" in db_url.lower():
            # Fix postgres:// to postgresql:// if needed
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            
            backup_path = backup_postgresql(db_url, output_dir)
        else:
            print(f"✗ Unsupported database type: {db_url}", file=sys.stderr)
            sys.exit(1)
        
        # Cleanup old backups (keep last 30 days)
        keep_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
        cleanup_old_backups(output_dir, keep_days)
        
        # Get backup size
        backup_size = os.path.getsize(backup_path)
        size_mb = backup_size / (1024 * 1024)
        print(f"✓ Backup completed successfully ({size_mb:.2f} MB)")
        print(f"  Backup location: {backup_path}")
        
    except Exception as e:
        print(f"✗ Backup failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

