"""
Database migration script to create initial tables
"""
import os
import sys
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.user import User
from app.models.campaign import Campaign, ConversationFlow, VoiceModel
from app.models.voter import Voter
from app.models.call_log import CallLog

def create_tables():
    """Create all database tables"""
    print("Creating database tables...")
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

def drop_tables():
    """Drop all database tables"""
    print("WARNING: This will drop all tables in the database!")
    confirmation = input("Are you sure you want to continue? (y/n): ")
    if confirmation.lower() != 'y':
        print("Operation cancelled.")
        return
    
    app = create_app()
    with app.app_context():
        db.drop_all()
        print("All database tables dropped successfully!")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--drop':
        drop_tables()
    else:
        create_tables()
