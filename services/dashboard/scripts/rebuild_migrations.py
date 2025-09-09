#!/usr/bin/env python
import os
import sys
import subprocess
import importlib.util
import shutil
import re
from pathlib import Path

# Determine the dashboard directory path regardless of where the script is run from
script_dir = os.path.dirname(os.path.abspath(__file__))
dashboard_dir = os.path.dirname(script_dir)  # Parent directory of scripts
sys.path.insert(0, dashboard_dir)

def run_script(script_path):
    """Run a Python script and print its output."""
    print(f"\n=== Running {script_path} ===")
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"Errors:\n{result.stderr}")
    return result.returncode == 0

def create_env_backup():
    """Create a backup of the env.py file."""
    env_path = Path(os.path.join(dashboard_dir, 'migrations', 'env.py'))
    backup_path = Path(os.path.join(dashboard_dir, 'migrations', 'env.py.bak'))
    
    if env_path.exists():
        shutil.copy(env_path, backup_path)
        print(f"Created backup of {env_path} to {backup_path}")
    else:
        print(f"Warning: {env_path} does not exist")

def restore_env_backup():
    """Restore the env.py file from backup."""
    env_path = Path(os.path.join(dashboard_dir, 'migrations', 'env.py'))
    backup_path = Path(os.path.join(dashboard_dir, 'migrations', 'env.py.bak'))
    
    if backup_path.exists():
        shutil.copy(backup_path, env_path)
        print(f"Restored {env_path} from {backup_path}")
    else:
        print(f"Warning: {backup_path} does not exist")

def create_metadata_dir():
    """Create the metadata directory if it doesn't exist."""
    os.makedirs(os.path.join(dashboard_dir, 'migrations', 'metadata'), exist_ok=True)

def check_dependencies():
    """Check if required packages are installed."""
    required_packages = ['sqlalchemy', 'alembic']
    missing_packages = []
    
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        print("Please install them with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def verify_migration_file(migration_path):
    """Verify that the generated migration file is valid and provide warnings."""
    if not os.path.exists(migration_path):
        print(f"Error: Migration file not found: {migration_path}")
        return False
        
    try:
        with open(migration_path, 'r') as f:
            content = f.read()
            
        # Check for syntax errors
        try:
            compile(content, migration_path, 'exec')
        except SyntaxError as e:
            print(f"Syntax error in migration file at line {e.lineno}, column {e.offset}")
            print(f"Error context: {e.text.strip() if e.text else ''}")
            return False
            
        # Check for TODO comments
        todo_matches = re.findall(r'# TODO: (.*)', content)
        if todo_matches:
            print("\n⚠️  Warning: The migration file contains TODOs that need attention:")
            for todo in todo_matches:
                print(f"  - {todo}")
            print("Please review these items before applying the migration.\n")
            
        # Check for raw SQL or text blocks
        if 'sa.text(' in content:
            print("\n⚠️  Note: The migration contains raw SQL expressions.")
            print("This is normal for setup/teardown operations but please review for correctness.\n")
            
        # Ensure all model columns are included
        print("\n✓ Migration file verified. Please review before applying.")
        
        return True
            
    except Exception as e:
        print(f"Error verifying migration file: {e}")
        return False

def list_most_recent_migration():
    """Find and display the most recently created migration file."""
    versions_dir = os.path.join(dashboard_dir, 'migrations', 'versions')
    if not os.path.exists(versions_dir):
        print("No versions directory found.")
        return None
    
    migration_files = [f for f in os.listdir(versions_dir) if f.endswith('.py')]
    if not migration_files:
        print("No migration files found.")
        return None
    
    # Sort by creation time, most recent first
    migration_files.sort(key=lambda f: os.path.getctime(os.path.join(versions_dir, f)), reverse=True)
    most_recent = migration_files[0]
    migration_path = os.path.join(versions_dir, most_recent)
    
    print(f"Most recent migration: {most_recent}")
    return migration_path

def validate_models_vs_migration(migration_path):
    """Validate that all model columns are included in the migration."""
    try:
        # Import the metadata from the JSON file
        metadata_path = os.path.join(dashboard_dir, 'migrations', 'metadata', 'model_metadata.json')
        if not os.path.exists(metadata_path):
            print("✗ Model metadata JSON not found. Cannot validate migration.")
            return False
            
        import json
        with open(metadata_path, 'r') as f:
            model_metadata = json.load(f)
            
        # Read the migration file
        with open(migration_path, 'r') as f:
            migration_content = f.read()
            
        # Check that all model tables are in the migration
        missing_tables = []
        for model_name, model_info in model_metadata.items():
            tablename = model_info['tablename']
            if f"'{tablename}'" not in migration_content:
                missing_tables.append(f"{tablename} ({model_name})")
                
        if missing_tables:
            print(f"✗ Migration is missing these tables: {', '.join(missing_tables)}")
            return False
            
        # Check that all columns are in the migration
        missing_columns = []
        for model_name, model_info in model_metadata.items():
            tablename = model_info['tablename']
            for column_name in model_info['columns'].keys():
                if f"'{column_name}'" not in migration_content:
                    missing_columns.append(f"{tablename}.{column_name}")
                    
        if missing_columns:
            print(f"✗ Migration is missing these columns: {', '.join(missing_columns)}")
            return False
            
        print("✓ All model tables and columns appear to be in the migration.")
        return True
    except Exception as e:
        print(f"Error validating models vs migration: {e}")
        return False

def generate_documentation(migration_path):
    """Generate documentation of the changes in the migration file."""
    # This could be expanded to create more detailed documentation
    # For now, it just creates a simple info file
    try:
        with open(migration_path, 'r') as f:
            content = f.read()
            
        # Extract tables created in the migration
        table_pattern = r"op\.create_table\(\s*'([^']+)'"
        tables = re.findall(table_pattern, content)
        
        # Extract indexes created
        index_pattern = r"op\.create_index\([^,]+, '([^']+)', \['([^']+)'\]"
        indexes = re.findall(index_pattern, content)
        
        # Create documentation file
        doc_file = migration_path.replace('.py', '_info.txt')
        with open(doc_file, 'w') as f:
            f.write(f"Migration Documentation\n")
            f.write(f"======================\n\n")
            
            f.write(f"Tables Created ({len(tables)}):\n")
            for table in tables:
                f.write(f"- {table}\n")
                
            f.write(f"\nIndexes Created ({len(indexes)}):\n")
            for table, column in indexes:
                f.write(f"- {table}.{column}\n")
                
        print(f"Created documentation: {doc_file}")
        return True
    except Exception as e:
        print(f"Error generating documentation: {e}")
        return False

def main():
    """Main function to rebuild migrations."""
    print("Starting migration rebuild process...")
    
    # Check dependencies
    if not check_dependencies():
        return
    
    # Create backup of env.py
    create_env_backup()
    
    # Create metadata directory
    create_metadata_dir()
    
    # Step 1: Extract model metadata
    metadata_script = os.path.join(script_dir, 'generate_migration_metadata.py')
    if not run_script(metadata_script):
        print("Failed to extract model metadata. Exiting.")
        return
    
    # Step 2: Generate migration from metadata
    migration_script = os.path.join(script_dir, 'generate_migration_from_metadata.py')
    if not run_script(migration_script):
        print("Failed to generate migration. Exiting.")
        restore_env_backup()
        return
    
    # Step 3: Verify and validate the generated migration file
    migration_path = list_most_recent_migration()
    if migration_path:
        verify_migration_file(migration_path)
        validate_models_vs_migration(migration_path)
        generate_documentation(migration_path)
    
    print("\n=== Migration rebuild complete ===")
    print("\nImportant steps before applying migration:")
    print("1. Review the generated migration file carefully")
    print("2. Pay special attention to foreign key constraints")
    print("3. Ensure table drop order won't violate constraints")
    print("4. Back up your database before applying")
    print("\nTo apply the migration on your remote database, run:")
    print("cd backend/services/dashboard && python -m alembic upgrade head")

if __name__ == '__main__':
    main() 