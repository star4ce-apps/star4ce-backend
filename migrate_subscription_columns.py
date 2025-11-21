#!/usr/bin/env python3
"""
Migration script to add subscription columns to the dealerships table.
Run this once to update your database schema.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import app and db
from app import app, db
from sqlalchemy import text

def migrate():
    """Add subscription columns to dealerships table if they don't exist."""
    with app.app_context():
        try:
            # Check database type
            db_url = os.getenv("DATABASE_URL", "")
            is_sqlite = "sqlite" in db_url.lower() or not db_url or "instance" in db_url
            
            if is_sqlite:
                # SQLite migration
                print("Detected SQLite database. Adding columns...")
                
                # SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS directly
                # We need to check if columns exist first
                conn = db.engine.connect()
                
                # Get table info
                result = conn.execute(text("PRAGMA table_info(dealerships)"))
                columns = [row[1] for row in result]
                
                columns_to_add = {
                    "stripe_customer_id": "VARCHAR(255)",
                    "stripe_subscription_id": "VARCHAR(255)",
                    "subscription_status": "VARCHAR(50) DEFAULT 'trial'",
                    "subscription_plan": "VARCHAR(50)",
                    "trial_ends_at": "DATETIME",
                    "subscription_ends_at": "DATETIME",
                    "created_at": "DATETIME",
                    "updated_at": "DATETIME"
                }
                
                for col_name, col_type in columns_to_add.items():
                    if col_name not in columns:
                        print(f"Adding column: {col_name}")
                        try:
                            conn.execute(text(f"ALTER TABLE dealerships ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                            print(f"✓ Added {col_name}")
                        except Exception as e:
                            print(f"✗ Error adding {col_name}: {e}")
                    else:
                        print(f"✓ Column {col_name} already exists")
                
                # Set default subscription_status for existing rows
                conn.execute(text("UPDATE dealerships SET subscription_status = 'trial' WHERE subscription_status IS NULL"))
                conn.commit()
                
                conn.close()
                print("\n✅ SQLite migration completed!")
                
            else:
                # PostgreSQL migration
                print("Detected PostgreSQL database. Adding columns...")
                conn = db.engine.connect()
                
                # PostgreSQL supports IF NOT EXISTS
                migrations = [
                    "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)",
                    "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255)",
                    "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'trial'",
                    "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50)",
                    "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP",
                    "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS subscription_ends_at TIMESTAMP",
                    "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS created_at TIMESTAMP",
                    "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
                ]
                
                for migration in migrations:
                    try:
                        conn.execute(text(migration))
                        conn.commit()
                        print(f"✓ Executed: {migration[:50]}...")
                    except Exception as e:
                        print(f"✗ Error: {e}")
                
                # Set default subscription_status for existing rows
                conn.execute(text("UPDATE dealerships SET subscription_status = 'trial' WHERE subscription_status IS NULL"))
                conn.commit()
                
                conn.close()
                print("\n✅ PostgreSQL migration completed!")
                
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    print("Starting database migration...")
    migrate()
    print("\nMigration script completed. You can now restart your backend.")

