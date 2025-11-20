#!/usr/bin/env python3
"""
Database Migration Runner
Applies database migrations for missed call queue system
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app.obs.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

class DatabaseMigrator:
    """Handles database migrations for missed call queue system"""
    
    def __init__(self):
        self.database_url = settings.DATABASE_URL
        self.engine = None
        
    def connect(self):
        """Connect to database"""
        try:
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=False  # Set to True for SQL debugging
            )
            logger.info("Connected to database successfully")
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise
    
    def run_migration(self, migration_file: str):
        """Run a specific migration file"""
        try:
            migration_path = Path(__file__).parent / "migrations" / migration_file
            
            if not migration_path.exists():
                logger.error(f"Migration file not found: {migration_path}")
                return False
            
            with open(migration_path, 'r') as f:
                migration_sql = f.read()
            
            logger.info(f"Running migration: {migration_file}")
            
            with self.engine.connect() as conn:
                # Begin transaction
                trans = conn.begin()
                try:
                    # Split SQL into individual statements for SQLite compatibility
                    statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
                    
                    for statement in statements:
                        if statement and not statement.startswith('--'):
                            conn.execute(text(statement))
                    
                    trans.commit()
                    logger.info(f"Migration {migration_file} completed successfully")
                    return True
                except Exception as e:
                    trans.rollback()
                    logger.error(f"Migration {migration_file} failed: {str(e)}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error running migration {migration_file}: {str(e)}")
            return False
    
    def check_migration_status(self):
        """Check which migrations have been applied"""
        try:
            # Create migrations table if it doesn't exist
            create_migrations_table = """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            with self.engine.connect() as conn:
                conn.execute(text(create_migrations_table))
                conn.commit()
            
            # Get applied migrations
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT migration_name FROM schema_migrations ORDER BY applied_at"))
                applied_migrations = [row[0] for row in result.fetchall()]
            
            logger.info(f"Applied migrations: {applied_migrations}")
            return applied_migrations
            
        except Exception as e:
            logger.error(f"Error checking migration status: {str(e)}")
            return []
    
    def mark_migration_applied(self, migration_name: str):
        """Mark a migration as applied"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO schema_migrations (migration_name) VALUES (:name) ON CONFLICT DO NOTHING"
                ), {"name": migration_name})
                conn.commit()
            logger.info(f"Marked migration {migration_name} as applied")
        except Exception as e:
            logger.error(f"Error marking migration as applied: {str(e)}")
    
    def run_all_migrations(self):
        """Run all pending migrations"""
        try:
            # Get list of migration files
            migrations_dir = Path(__file__).parent / "migrations"
            migration_files = sorted([f for f in migrations_dir.glob("*.sql")])
            
            if not migration_files:
                logger.warning("No migration files found")
                return True
            
            applied_migrations = self.check_migration_status()
            
            success_count = 0
            for migration_file in migration_files:
                migration_name = migration_file.name
                
                if migration_name in applied_migrations:
                    logger.info(f"Migration {migration_name} already applied, skipping")
                    continue
                
                logger.info(f"Applying migration: {migration_name}")
                
                if self.run_migration(migration_name):
                    self.mark_migration_applied(migration_name)
                    success_count += 1
                else:
                    logger.error(f"Migration {migration_name} failed, stopping")
                    return False
            
            logger.info(f"Successfully applied {success_count} migrations")
            return True
            
        except Exception as e:
            logger.error(f"Error running migrations: {str(e)}")
            return False
    
    def rollback_migration(self, migration_name: str):
        """Rollback a specific migration (if supported)"""
        logger.warning(f"Rollback for {migration_name} not implemented - manual rollback required")
        return False
    
    def verify_migration(self, migration_name: str):
        """Verify a migration was applied correctly"""
        try:
            # Check if required tables exist
            required_tables = [
                'missed_call_queue',
                'missed_call_queue_audit',
                'sms_dead_letter_queue',
                'circuit_breaker_state',
                'rate_limit_tracking',
                'abuse_detection',
                'event_deduplication'
            ]
            
            with self.engine.connect() as conn:
                for table in required_tables:
                    result = conn.execute(text(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = '{table}'
                        );
                    """))
                    
                    if not result.fetchone()[0]:
                        logger.error(f"Required table {table} not found")
                        return False
                
                logger.info("All required tables exist")
                return True
                
        except Exception as e:
            logger.error(f"Error verifying migration: {str(e)}")
            return False

def main():
    """Main migration runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Database Migration Runner')
    parser.add_argument('--migration', help='Run specific migration file')
    parser.add_argument('--all', action='store_true', help='Run all pending migrations')
    parser.add_argument('--status', action='store_true', help='Check migration status')
    parser.add_argument('--verify', help='Verify specific migration')
    
    args = parser.parse_args()
    
    migrator = DatabaseMigrator()
    
    try:
        migrator.connect()
        
        if args.status:
            migrator.check_migration_status()
        elif args.migration:
            success = migrator.run_migration(args.migration)
            if success:
                migrator.mark_migration_applied(args.migration)
                migrator.verify_migration(args.migration)
        elif args.all:
            success = migrator.run_all_migrations()
            if success:
                logger.info("All migrations completed successfully")
            else:
                logger.error("Migration failed")
                sys.exit(1)
        elif args.verify:
            migrator.verify_migration(args.verify)
        else:
            logger.info("No action specified. Use --help for options")
            
    except Exception as e:
        logger.error(f"Migration runner failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
