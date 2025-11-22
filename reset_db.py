#!/usr/bin/env python3
"""
Simple script to reset the database (delete and recreate all tables).
Works with both SQLite and PostgreSQL.
"""

import os
import sys

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add the current directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Flask app and database
from app import app, db

def reset_database():
    """Delete/drop all tables and recreate them."""
    with app.app_context():
        # Get database URL
        db_url = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        
        print("🔄 Resetting database...")
        print(f"   Database: {db_url}")
        
        # Check if it's SQLite
        if db_url.startswith("sqlite:///"):
            # For SQLite, we need to close all connections before deleting the file
            # This is especially important on Windows where SQLite locks the file
            print("   Closing all database connections...")
            try:
                db.session.close()
                db.engine.dispose()
                print("   ✅ All connections closed")
            except Exception as e:
                print(f"   ⚠️  Warning while closing connections: {e}")
            
            # For SQLite, we can just delete the file
            db_path = db_url.replace("sqlite:///", "")
            
            # Handle Windows paths
            if "\\" in db_path or "/" in db_path:
                # It's a path
                if os.path.exists(db_path):
                    print(f"   Deleting SQLite database file: {db_path}")
                    try:
                        os.remove(db_path)
                        print("   ✅ Database file deleted")
                    except PermissionError:
                        print("   ❌ Error: Cannot delete database file - it may be in use.")
                        print("   💡 Tip: Make sure the Flask server is not running.")
                        return False
                    except Exception as e:
                        print(f"   ❌ Error deleting database file: {e}")
                        return False
                else:
                    print(f"   ⚠️  Database file not found: {db_path}")
            else:
                # Relative path, try to find it
                possible_paths = [
                    db_path,
                    os.path.join("instance", db_path),
                    os.path.join(os.path.dirname(__file__), "instance", db_path)
                ]
                deleted = False
                for path in possible_paths:
                    if os.path.exists(path):
                        print(f"   Deleting SQLite database file: {path}")
                        try:
                            os.remove(path)
                            print("   ✅ Database file deleted")
                            deleted = True
                            break
                        except PermissionError:
                            print(f"   ❌ Error: Cannot delete database file at {path} - it may be in use.")
                            print("   💡 Tip: Make sure the Flask server is not running.")
                            return False
                        except Exception as e:
                            print(f"   ❌ Error deleting database file: {e}")
                            return False
                if not deleted:
                    print(f"   ⚠️  Database file not found (tried: {', '.join(possible_paths)})")
        else:
            # For PostgreSQL, drop all tables
            print("   Dropping all tables from PostgreSQL database...")
            try:
                db.drop_all()
                print("   ✅ All tables dropped")
            except Exception as e:
                print(f"   ⚠️  Error dropping tables: {e}")
                print("   Continuing anyway...")
        
        # Recreate all tables
        print("\n📦 Creating all tables...")
        try:
            db.create_all()
            print("   ✅ All tables created successfully!")
            
            # Run migrations if needed (from app.py)
            try:
                from sqlalchemy import text, inspect
                inspector = inspect(db.engine)
                
                # Check if is_approved column exists
                try:
                    columns = [col['name'] for col in inspector.get_columns('users')]
                    
                    if 'is_approved' not in columns:
                        print("   Running migrations...")
                        with db.engine.connect() as conn:
                            if 'postgresql' in str(db.engine.url):
                                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT FALSE"))
                                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP"))
                                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_by INTEGER"))
                            else:
                                conn.execute(text("ALTER TABLE users ADD COLUMN is_approved BOOLEAN NOT NULL DEFAULT 0"))
                                conn.execute(text("ALTER TABLE users ADD COLUMN approved_at DATETIME"))
                                conn.execute(text("ALTER TABLE users ADD COLUMN approved_by INTEGER"))
                            
                            conn.execute(text("UPDATE users SET is_approved = TRUE WHERE role != 'manager'"))
                            conn.commit()
                        print("   ✅ Migrations completed")
                except Exception as e:
                    print(f"   ⚠️  Migration check skipped: {e}")
            except Exception as e:
                print(f"   ⚠️  Migration check skipped: {e}")
            
        except Exception as e:
            print(f"   ❌ Error creating tables: {e}")
            return False
        
        print("\n✅ Database reset complete!")
        return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Reset the database (delete and recreate all tables)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    
    print("=" * 60)
    print("🗑️  Database Reset Script")
    print("=" * 60)
    print()
    
    if not args.yes:
        confirm = input("⚠️  This will DELETE ALL DATA. Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Cancelled.")
            sys.exit(0)
        print()
    else:
        print("⚠️  Resetting database (--yes flag used)...")
        print()
    
    success = reset_database()
    
    if success:
        print("\n🎉 Database is now empty and ready for testing!")
    else:
        print("\n❌ Database reset failed. Check errors above.")
        sys.exit(1)

