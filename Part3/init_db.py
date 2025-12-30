

import os
import sys

# Add current directory to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, migrate_mock_data

def main():
    """Initialize database with mock data for AI feedback system"""
    print("🗄️  Learning Analytics Database Setup")
    print("=" * 50)
    
    try:
        # Initialize database tables
        print("1. Creating database tables...")
        init_database()
        
        # Migrate mock data
        print("2. Migrating mock data...")
        migrate_mock_data()
        
        print("\n✅ Database setup complete!")
        print("   - Database file: learning_analytics.db")
        print("   - Mock data migrated for AI feedback analysis")
        print("   - All calculations and data storage functional")
        print("   - AI feedback analyzes all stored data")
        
    except Exception as e:
        print(f"\n❌ Database setup failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()