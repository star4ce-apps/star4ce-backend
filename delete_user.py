#!/usr/bin/env python3
"""Quick script to delete a user from the database"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

from app import app, db, User

def delete_user(email_or_id):
    with app.app_context():
        # Try to find by email first
        user = User.query.filter_by(email=email_or_id).first()
        
        # If not found, try by ID
        if not user:
            try:
                user_id = int(email_or_id)
                user = User.query.get(user_id)
            except ValueError:
                pass
        
        if not user:
            print(f"❌ User not found: {email_or_id}")
            return False
        
        print(f"Found user: {user.email} (ID: {user.id}, Role: {user.role})")
        confirm = input("Delete this user? (yes/no): ")
        
        if confirm.lower() == 'yes':
            db.session.delete(user)
            db.session.commit()
            print(f"✅ Deleted user: {user.email}")
            return True
        else:
            print("❌ Cancelled")
            return False

def list_users():
    """List all users"""
    with app.app_context():
        users = User.query.order_by(User.created_at.desc()).all()
        print(f"\n📋 All Users ({len(users)} total):\n")
        print(f"{'ID':<5} {'Email':<40} {'Role':<15} {'Verified':<10} {'Approved':<10}")
        print("-" * 90)
        for u in users:
            print(f"{u.id:<5} {u.email:<40} {u.role:<15} {'Yes' if u.is_verified else 'No':<10} {'Yes' if u.is_approved else 'No':<10}")
        print()

def delete_user_by_email(email):
    """Delete user by email"""
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"❌ User not found: {email}")
            return False
        
        print(f"Found: {user.email} (ID: {user.id}, Role: {user.role})")
        confirm = input("Delete? (yes/no): ")
        
        if confirm.lower() == 'yes':
            db.session.delete(user)
            db.session.commit()
            print(f"✅ Deleted: {user.email}")
            return True
        else:
            print("❌ Cancelled")
            return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python delete_user.py list                    # List all users")
        print("  python delete_user.py <email>                 # Delete user by email")
        print("  python delete_user.py <id>                    # Delete user by ID")
        print("\nExamples:")
        print("  python delete_user.py list")
        print("  python delete_user.py user@example.com")
        print("  python delete_user.py 123")
        sys.exit(1)
    
    if sys.argv[1].lower() == 'list':
        list_users()
    elif '@' in sys.argv[1]:
        # Looks like an email
        delete_user_by_email(sys.argv[1])
    else:
        delete_user(sys.argv[1])

