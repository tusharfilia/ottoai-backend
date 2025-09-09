#!/usr/bin/env python
import os
import sys
import datetime
import uuid
import shutil
import re
import json

# Determine the dashboard directory path regardless of where the script is run from
script_dir = os.path.dirname(os.path.abspath(__file__))
dashboard_dir = os.path.dirname(script_dir)  # Parent directory of scripts
sys.path.insert(0, dashboard_dir)

def fix_column_constraints(type_name, constraints):
    """Convert constraints to SQLAlchemy format parameters"""
    params = []
    
    # Type is mandatory
    if type_name.lower() == 'string':
        params.append('sa.String()')
    elif type_name.lower() == 'integer':
        params.append('sa.Integer()')
    elif type_name.lower() == 'boolean':
        params.append('sa.Boolean()')
    elif type_name.lower() == 'float':
        params.append('sa.Float()')
    elif type_name.lower() == 'datetime':
        params.append('sa.DateTime()')
    elif type_name.lower() == 'text':
        params.append('sa.Text()')
    elif type_name.lower() == 'json':
        params.append('sa.JSON()')
    else:
        # For other types, just use the provided type name
        params.append(f'sa.{type_name}')
    
    # Process constraints
    for constraint in constraints:
        if constraint == "PRIMARY KEY":
            params.append('primary_key=True')
        elif constraint == "NOT NULL":
            params.append('nullable=False')
        elif constraint == "UNIQUE":
            params.append('unique=True')
        elif constraint.startswith("DEFAULT "):
            # Extract the default value
            value = constraint[8:]  # Remove "DEFAULT " prefix
            
            if value == "<function>":
                # For functions like datetime.utcnow, use server_default with CURRENT_TIMESTAMP
                params.append("server_default=sa.text('CURRENT_TIMESTAMP')")
            elif value == "<expression>":
                # For complex expressions, use a generic server_default
                params.append("server_default=sa.text('NULL')")
            else:
                # Special handling for string literals
                if value.startswith('"') and value.endswith('"'):
                    # Convert double-quoted strings to properly escaped single quotes for SQL
                    inner_value = value[1:-1]  # Remove the quotes
                    # Need to escape single quotes in the string for SQL
                    inner_value = inner_value.replace("'", "''")
                    params.append(f"server_default=sa.text('\\''{inner_value}\\'')")
                else:
                    # Handle booleans specially
                    if value.lower() == 'true':
                        params.append("server_default=sa.text('TRUE')")
                    elif value.lower() == 'false':
                        params.append("server_default=sa.text('FALSE')")
                    else:
                        # For other literals
                        params.append(f"server_default=sa.text('{value}')")
        elif constraint.startswith("SERVER_DEFAULT "):
            # Extract the server default value
            value = constraint[14:]  # Remove "SERVER_DEFAULT " prefix
            
            # For explicit sa.text already
            if value.startswith('sa.text'):
                # Fix string literals inside text() - make sure they use single quotes
                value = re.sub(r'sa\.text\("([^"]*)"\)', r"sa.text('\1')", value)
                params.append(f"server_default={value}")
            else:
                params.append(f"server_default=sa.text('{value}')")
        elif constraint.startswith("FOREIGN KEY "):
            # Extract the target table and column
            target = constraint[12:]  # Remove "FOREIGN KEY " prefix
            params.append(f"sa.ForeignKey('{target}')")
    
    return ", ".join(params)

def verify_migration_code(file_path):
    """Verify the migration code doesn't have syntax errors."""
    try:
        with open(file_path, 'r') as f:
            migration_code = f.read()
            
        # Try to compile the code to check syntax
        compile(migration_code, file_path, 'exec')
        print(f"✓ Migration file syntax check passed: {file_path}")
        return True
    except SyntaxError as e:
        print(f"✗ Syntax error in migration file: {e}")
        print(f"  at line {e.lineno}, column {e.offset}")
        print(f"  {e.text.strip() if e.text else ''}")
        
        # Try to automatically fix common syntax errors
        fixed = False
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Fix various syntax issues
        if fixed:
            print("Attempting to fix syntax errors automatically...")
            with open(file_path, 'w') as f:
                f.write(content)
            
            # Try to verify again
            return verify_migration_code(file_path)
        return False
    except Exception as e:
        print(f"✗ Error verifying migration file: {e}")
        return False

def get_foreign_key_dependencies(metadata):
    """Analyze metadata to determine table dependencies for proper drop order."""
    dependencies = {}
    
    # Initialize dependencies for all tables
    for model_name, model_info in metadata.items():
        table_name = model_info['tablename']
        dependencies[table_name] = []
    
    # Add foreign key dependencies
    for model_name, model_info in metadata.items():
        table_name = model_info['tablename']
        for col_name, col_info in model_info['columns'].items():
            for constraint in col_info['constraints']:
                if constraint.startswith('FOREIGN KEY '):
                    # Extract referenced table from "FOREIGN KEY table.column"
                    parts = constraint[12:].split('.')
                    if len(parts) == 2:
                        referenced_table = parts[0]
                        if referenced_table != table_name:  # Skip self-references
                            dependencies[table_name].append(referenced_table)
    
    return dependencies

def topological_sort(dependencies):
    """Sort tables by dependencies to ensure proper drop order."""
    # Initialize result and visited sets
    result = []
    visited = set()
    temp_visited = set()  # For cycle detection
    
    def visit(node):
        if node in temp_visited:
            # Cyclic dependency found
            return False
        if node in visited:
            return True
        
        temp_visited.add(node)
        
        # Visit all dependencies
        for dep in dependencies.get(node, []):
            if dep in dependencies:  # Make sure dependency exists
                if not visit(dep):
                    return False
        
        temp_visited.remove(node)
        visited.add(node)
        result.append(node)
        return True
    
    # Visit all nodes
    for node in list(dependencies.keys()):
        if node not in visited:
            if not visit(node):
                print(f"Warning: Cyclic dependency found involving {node}")
                # Just add the node in this case
                if node not in result:
                    result.append(node)
    
    return result

def fix_string_literals_in_migration(file_path):
    """Post-process the migration file to fix string literals"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Fix status VARCHAR DEFAULT "pending" -> status VARCHAR DEFAULT 'pending'
        content = re.sub(r'server_default=sa\.text\("([^"]*)"\)', r"server_default=sa.text('\1')", content)
        
        # Find lines with server_default and check if they have proper quotes
        for line in content.split('\n'):
            if 'server_default=sa.text(' in line:
                if not (line.count("'") >= 2):  # Should have at least 2 single quotes
                    print(f"Warning: Possibly malformed server_default in line: {line}")
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"Error fixing string literals: {e}")
        return False

def generate_migration():
    """Generate an Alembic migration from the extracted model metadata."""
    metadata_dir = os.path.join(dashboard_dir, 'migrations', 'metadata')
    metadata_file = os.path.join(metadata_dir, 'model_metadata.py')
    json_metadata_file = os.path.join(metadata_dir, 'model_metadata.json')
    
    # Try to load the JSON metadata first (easier to parse)
    if os.path.exists(json_metadata_file):
        try:
            with open(json_metadata_file, 'r') as f:
                MODEL_METADATA = json.load(f)
            print(f"Loaded metadata from JSON: {json_metadata_file}")
        except Exception as e:
            print(f"Error loading JSON metadata: {e}")
            MODEL_METADATA = None
    
    # Fall back to Python metadata if JSON not available
    if not os.path.exists(json_metadata_file) or MODEL_METADATA is None:
        if not os.path.exists(metadata_file):
            print(f"Error: Model metadata not found at {metadata_file}")
            print("Run generate_migration_metadata.py first.")
            return False
        
        try:
            # Import the metadata
            sys.path.append(metadata_dir)
            from model_metadata import MODEL_METADATA
            print(f"Loaded metadata from Python module: {metadata_file}")
        except ImportError as e:
            print(f"Error importing model metadata: {e}")
            return False

    # Read the most recent migration ID
    migration_txt = os.path.join(dashboard_dir, 'migrations', 'most_recent_migration.txt')
    
    if not os.path.exists(migration_txt):
        print(f"Error: Most recent migration file not found at {migration_txt}")
        return False
        
    with open(migration_txt, 'r') as f:
        most_recent_id = f.read().strip()

    # Use the correct parent revision ID
    parent_revision = most_recent_id
    
    # Generate a new migration ID
    new_migration_id = uuid.uuid4().hex[:12]
    
    # Create a timestamp for the migration filename
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    migration_filename = f"{timestamp}_{new_migration_id}_recreate_all_tables.py"
    versions_dir = os.path.join(dashboard_dir, 'migrations', 'versions')
    
    if not os.path.exists(versions_dir):
        os.makedirs(versions_dir, exist_ok=True)
        
    migration_path = os.path.join(versions_dir, migration_filename)
    
    # Create a sorted list of tables based on dependencies
    table_to_model = {model_info['tablename']: model_name for model_name, model_info in MODEL_METADATA.items()}
    dependencies = get_foreign_key_dependencies(MODEL_METADATA)
    
    # Get tables in dependency order for proper dropping
    sorted_tables = topological_sort(dependencies)
    sorted_tables.reverse()  # Reverse to drop dependent tables first
    
    # Generate the migration file
    print(f"Generating migration file: {migration_path}")
    
    with open(migration_path, 'w') as f:
        # Write migration header
        f.write(f'"""recreate_all_tables\n\n')
        f.write(f'Revision ID: {new_migration_id}\n')
        f.write(f'Revises: {parent_revision}\n')
        f.write(f'Create Date: {datetime.datetime.now().isoformat()}\n\n')
        f.write('"""\n\n')
        
        # Write imports
        f.write('from alembic import op\n')
        f.write('import sqlalchemy as sa\n')
        f.write('from sqlalchemy.sql import text\n\n\n')
        
        # Write revision identifiers
        f.write('# revision identifiers, used by Alembic.\n')
        f.write(f"revision = '{new_migration_id}'\n")
        f.write(f"down_revision = '{parent_revision}'\n")
        f.write('branch_labels = None\n')
        f.write('depends_on = None\n\n\n')
        
        # Write upgrade function
        f.write('def upgrade():\n')
        f.write('    # Use raw SQL to disable constraints and drop tables with CASCADE\n')
        f.write('    conn = op.get_bind()\n')
        f.write('    \n')
        f.write('    # Disable all constraints\n')
        f.write('    conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))\n')
        f.write('    \n')
        f.write('    # Drop all tables defined in the migration (in reverse dependency order)\n')
        
        # Write DROP statements for all tables
        for table_name in sorted_tables:
            f.write(f'    conn.execute(text(\'DROP TABLE IF EXISTS "{table_name}" CASCADE\'))\n')
        
        f.write('\n    # Create all tables in dependency order\n')
        
        # Reverse the order for table creation (create dependency tables first)
        sorted_tables.reverse()
        
        # Write CREATE statements for all tables
        for table_name in sorted_tables:
            if table_name in table_to_model:
                model_name = table_to_model[table_name]
                model_info = MODEL_METADATA[model_name]
                
                f.write(f'    op.create_table(\n')
                f.write(f"        '{table_name}',\n")
                
                # Write column declarations
                for col_name, col_info in model_info['columns'].items():
                    constraints_str = fix_column_constraints(col_info['type'], col_info['constraints'])
                    f.write(f"        sa.Column('{col_name}', {constraints_str}),\n")
                
                # Close the table creation
                f.write('    )\n\n')
        
        # Write simple index creation statements where needed
        for model_name, model_info in MODEL_METADATA.items():
            table_name = model_info['tablename']
            # Check for unique columns that might need indexes
            for col_name, col_info in model_info['columns'].items():
                if "UNIQUE" in col_info['constraints']:
                    f.write(f"    op.create_index(op.f('ix_{table_name}_{col_name}'), '{table_name}', ['{col_name}'], unique=True)\n")
        
        f.write('\n    # Re-enable constraints\n')
        f.write('    conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))\n')
        
        # Write downgrade function
        f.write('\n\ndef downgrade():\n')
        f.write('    # Drop all tables with CASCADE\n')
        f.write('    conn = op.get_bind()\n')
        f.write('    conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))\n')
        
        for table_name in sorted_tables:
            f.write(f'    conn.execute(text(\'DROP TABLE IF EXISTS "{table_name}" CASCADE\'))\n')
        
        f.write('    conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))\n')
    
    # Fix string literals as a post-processing step
    print("Fixing string literals in migration file...")
    fix_string_literals_in_migration(migration_path)
    
    # Verify the migration file
    if verify_migration_code(migration_path):
        # Update the most recent migration ID
        with open(migration_txt, 'w') as f:
            f.write(new_migration_id)
        print(f"✓ Updated most recent migration to: {new_migration_id}")
        print(f"✓ Migration successfully generated: {migration_path}")
        return True
    else:
        print(f"✗ Error in generated migration. Please fix manually: {migration_path}")
        return False

if __name__ == '__main__':
    generate_migration() 