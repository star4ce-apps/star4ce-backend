#!/usr/bin/env python3
"""
Database restore script for Star4ce.
Restores from a backup file (SQLite .db or PostgreSQL .sql).

Usage:
    python3 restore_database.py <backup_file> [--confirm]
    
WARNING: This will overwrite your current database!
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def restore_sqlite(backup_path: str, db_path: str, confirm: bool = False):
    """Restore SQLite database from backup file."""
    if not os.path.exists(backup_path):
        print(f"✗ Backup file not found: {backup_path}", file=sys.stderr)
        sys.exit(1)
    
    if not confirm:
        print("⚠️  WARNING: This will overwrite your current database!")
        print(f"   Backup file: {backup_path}")
        print(f"   Target database: {db_path}")
        response = input("   Type 'YES' to confirm: ")
        if response != "YES":
            print("Restore cancelled.")
            sys.exit(0)
    
    # Ensure target directory exists
    target_dir = os.path.dirname(db_path)
    if target_dir and not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    
    # Backup current database first (if it exists)
    if os.path.exists(db_path):
        current_backup = f"{db_path}.pre_restore_{os.path.getmtime(db_path)}"
        shutil.copy2(db_path, current_backup)
        print(f"✓ Current database backed up to: {current_backup}")
    
    # Copy backup file to database location
    shutil.copy2(backup_path, db_path)
    print(f"✓ Database restored from: {backup_path}")

def restore_postgresql(backup_path: str, db_url: str, confirm: bool = False):
    """Restore PostgreSQL database from backup file."""
    if not os.path.exists(backup_path):
        print(f"✗ Backup file not found: {backup_path}", file=sys.stderr)
        sys.exit(1)
    
    if not confirm:
        print("⚠️  WARNING: This will overwrite your current database!")
        print(f"   Backup file: {backup_path}")
        print(f"   Target database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
        response = input("   Type 'YES' to confirm: ")
        if response != "YES":
            print("Restore cancelled.")
            sys.exit(0)
    
    # Parse database URL
    import re
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
    if not match:
        raise ValueError(f"Invalid PostgreSQL URL format: {db_url}")
    
    user, password, host, port, database = match.groups()
    
    # Set PGPASSWORD environment variable
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    
    # Determine backup format
    if backup_path.endswith('.sql'):
        # Plain SQL dump
        cmd = ['psql', '-h', host, '-p', port, '-U', user, '-d', database, '-f', backup_path]
    else:
        # Custom format (compressed)
        cmd = ['pg_restore', '-h', host, '-p', port, '-U', user, '-d', database, '-c', backup_path]
    
    try:
        result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        print(f"✓ Database restored from: {backup_path}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Restore failed: {e.stderr}", file=sys.stderr)
        raise
    except FileNotFoundError:
        print("✗ PostgreSQL client tools not found. Install PostgreSQL client.", file=sys.stderr)
        raise

def list_backups(backup_dir: str):
    """List available backup files."""
    if not os.path.exists(backup_dir):
        print(f"No backup directory found: {backup_dir}")
        return
    
    backups = []
    for filename in os.listdir(backup_dir):
        filepath = os.path.join(backup_dir, filename)
        if os.path.isfile(filepath) and ('backup' in filename.lower() or filename.endswith('.sql') or filename.endswith('.db')):
            mtime = os.path.getmtime(filepath)
            size = os.path.getsize(filepath)
            backups.append((filename, mtime, size))
    
    if not backups:
        print("No backup files found.")
        return
    
    # Sort by modification time (newest first)
    backups.sort(key=lambda x: x[1], reverse=True)
    
    print(f"Available backups in {backup_dir}:")
    print()
    for i, (filename, mtime, size) in enumerate(backups, 1):
        from datetime import datetime
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_mb = size / (1024 * 1024)
        print(f"  {i}. {filename}")
        print(f"     Date: {date_str}")
        print(f"     Size: {size_mb:.2f} MB")
        print()

def main():
    """Main restore function."""
    if len(sys.argv) < 2:
        print("Usage: python3 restore_database.py <backup_file> [--confirm]")
        print("       python3 restore_database.py --list")
        print()
        print("Options:")
        print("  --confirm    Skip confirmation prompt")
        print("  --list       List available backups")
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        backup_dir = os.getenv("BACKUP_DIR", "backups")
        list_backups(backup_dir)
        sys.exit(0)
    
    backup_path = sys.argv[1]
    confirm = "--confirm" in sys.argv
    
    # Get database URL
    db_url = os.getenv("DATABASE_URL", "sqlite:///instance/star4ce.db")
    
    print(f"Restoring database from backup...")
    print(f"Backup file: {backup_path}")
    print(f"Target database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print()
    
    try:
        if "sqlite" in db_url.lower():
            # Extract SQLite file path
            db_path = db_url.replace("sqlite:///", "")
            if not os.path.isabs(db_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                db_path = os.path.join(script_dir, db_path)
            
            # Handle instance folder path
            if not os.path.exists(os.path.dirname(db_path)) or not os.path.exists(db_path):
                # Try with instance/ prefix
                instance_path = os.path.join(script_dir, "instance", os.path.basename(db_path))
                if os.path.exists(instance_path) or os.path.exists(os.path.dirname(instance_path)):
                    db_path = instance_path
                else:
                    # Default to instance/star4ce.db
                    db_path = os.path.join(script_dir, "instance", "star4ce.db")
            
            restore_sqlite(backup_path, db_path, confirm)
        elif "postgresql" in db_url.lower() or "postgres" in db_url.lower():
            # Fix postgres:// to postgresql:// if needed
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            
            restore_postgresql(backup_path, db_url, confirm)
        else:
            print(f"✗ Unsupported database type: {db_url}", file=sys.stderr)
            sys.exit(1)
        
        print("✓ Restore completed successfully!")
        
    except Exception as e:
        print(f"✗ Restore failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

