#!/usr/bin/env python
import os
import sys
import importlib
import inspect
import json
import pkgutil
import re
from pathlib import Path

# Add the parent directory to path so we can import app modules
script_dir = os.path.dirname(os.path.abspath(__file__))
dashboard_dir = os.path.dirname(script_dir)
sys.path.insert(0, dashboard_dir)

# First let's create a mock for SQLAlchemy to avoid database connection
class MockBase:
    """Mock SQLAlchemy Base class to avoid database connection"""
    __subclasses__ = []
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        MockBase.__subclasses__.append(cls)

# Store the original imports to restore later
original_import = __builtins__.__import__

def patched_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Patch the import function to mock SQLAlchemy database dependencies"""
    if name == 'sqlalchemy' or name.startswith('sqlalchemy.'):
        # Return our mocked module for SQLAlchemy
        if 'sqlalchemy.orm' in name or name == 'sqlalchemy.orm':
            # Create mock sqlalchemy.orm module with relationship function
            import types
            mock_module = types.ModuleType('sqlalchemy.orm')
            mock_module.relationship = lambda *args, **kwargs: None
            mock_module.declarative_base = lambda: MockBase
            return mock_module
        elif 'sqlalchemy.ext.declarative' in name:
            # Create mock sqlalchemy.ext.declarative module
            import types
            mock_module = types.ModuleType('sqlalchemy.ext.declarative')
            mock_module.declarative_base = lambda: MockBase
            return mock_module
    
    # For app.database, return our mocked Base
    if name == 'app.database':
        # Create mock database module with Base
        import types
        mock_module = types.ModuleType('app.database')
        mock_module.Base = MockBase
        return mock_module
        
    # For other imports, use the original import function
    return original_import(name, globals, locals, fromlist, level)

def normalize_quotes(value_str):
    """Normalize quotes in string values, handling nested quotes properly"""
    if value_str is None:
        return None
    
    value_str = value_str.strip()
    
    # If it's already quoted, extract the content
    if (value_str.startswith('"') and value_str.endswith('"')) or (value_str.startswith("'") and value_str.endswith("'")):
        # Extract content without quotes
        content = value_str[1:-1]
        # For SQL compatibility, all string literals should use single quotes
        # Escape any single quotes in the content for SQL
        content = content.replace("'", "''")
        return f"'{content}'"
    
    # For boolean values, standardize format
    if value_str.lower() == 'true':
        return "TRUE"
    elif value_str.lower() == 'false':
        return "FALSE"
    
    # For function calls like datetime.utcnow
    if 'datetime.utcnow' in value_str or 'datetime.datetime.utcnow' in value_str:
        return "<function>"
    
    # For SQL server-side default expressions
    if value_str.lower() == 'current_timestamp':
        return "CURRENT_TIMESTAMP"
    
    # For numeric values, keep as is
    if value_str.isdigit() or (value_str.startswith('-') and value_str[1:].isdigit()):
        return value_str
    
    # For float values
    try:
        float(value_str)
        return value_str
    except ValueError:
        pass
    
    # If not recognized as a specific type, treat as string
    return f"'{value_str}'"

def extract_model_info_from_file(file_path):
    """Extract model information directly from Python file using regex parsing"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    models = {}
    
    # Find class definitions that inherit from Base
    class_pattern = r'class\s+(\w+)\s*\(.*Base.*\):'
    for match in re.finditer(class_pattern, content):
        model_name = match.group(1)
        
        # Find tablename
        tablename_pattern = r'__tablename__\s*=\s*[\'"]([^\'"]+)[\'"]'
        tablename_match = re.search(tablename_pattern, content[match.start():])
        if not tablename_match:
            print(f"Warning: Model {model_name} has no tablename defined. Skipping.")
            continue
        
        tablename = tablename_match.group(1)
        
        # Find column definitions
        columns = {}
        column_pattern = r'(\w+)\s*=\s*Column\(([^)]+)\)'
        for col_match in re.finditer(column_pattern, content[match.start():]):
            col_name = col_match.group(1)
            col_def = col_match.group(2)
            
            # Extract column type and constraints
            constraints = []
            
            # Extract type - look for first token before a comma or parenthesis
            type_pattern = r'([A-Za-z0-9_]+)'
            type_match = re.search(type_pattern, col_def)
            if not type_match:
                print(f"Warning: Could not determine type for column {model_name}.{col_name}. Using String.")
                col_type = "String"
            else:
                col_type = type_match.group(1)
            
            # Check for primary_key
            if re.search(r'primary_key\s*=\s*True', col_def, re.IGNORECASE):
                constraints.append("PRIMARY KEY")
            
            # Check for nullable
            if re.search(r'nullable\s*=\s*False', col_def, re.IGNORECASE):
                constraints.append("NOT NULL")
            
            # Check for unique
            if re.search(r'unique\s*=\s*True', col_def, re.IGNORECASE):
                constraints.append("UNIQUE")
            
            # Check for default
            default_pattern = r'default\s*=\s*([^,\)]+)'
            default_match = re.search(default_pattern, col_def)
            if default_match:
                default_value = default_match.group(1).strip()
                
                # Handle callable defaults like datetime.utcnow
                if 'datetime.utcnow' in default_value or 'datetime.datetime.utcnow' in default_value:
                    constraints.append("DEFAULT <function>")
                else:
                    # Normalize string literals
                    norm_value = normalize_quotes(default_value)
                    constraints.append(f"DEFAULT {norm_value}")
            
            # Check for server_default
            server_default_pattern = r'server_default\s*=\s*([^,\)]+)'
            server_default_match = re.search(server_default_pattern, col_def)
            if server_default_match:
                server_default = server_default_match.group(1).strip()
                
                # Handle sa.text expressions
                text_pattern = r'(?:sa\.)?text\(\s*([\'"][^\'"]+[\'"]\s*)\)'
                text_match = re.search(text_pattern, server_default)
                if text_match:
                    text_value = text_match.group(1).strip()
                    # Normalize quotes
                    text_value = normalize_quotes(text_value)
                    constraints.append(f"SERVER_DEFAULT {text_value}")
                else:
                    constraints.append(f"SERVER_DEFAULT {server_default}")
            
            # Check for foreign key
            fk_pattern = r'ForeignKey\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
            fk_match = re.search(fk_pattern, col_def)
            if fk_match:
                fk_target = fk_match.group(1)
                constraints.append(f"FOREIGN KEY {fk_target}")
            
            columns[col_name] = {
                "type": col_type,
                "constraints": constraints
            }
        
        models[model_name] = {
            "tablename": tablename,
            "columns": columns
        }
    
    return models

def get_all_model_metadata():
    """Extract metadata from all model files without importing them."""
    models_dir = os.path.join(dashboard_dir, 'app', 'models')
    
    if not os.path.exists(models_dir):
        print(f"Error: Models directory not found at {models_dir}")
        return {}
    
    all_metadata = {}
    
    # Find all Python files in models directory
    for file_name in os.listdir(models_dir):
        if file_name.endswith('.py') and not file_name.startswith('_'):
            file_path = os.path.join(models_dir, file_name)
            print(f"Processing model file: {file_path}")
            
            # Extract model info from file
            model_info = extract_model_info_from_file(file_path)
            
            # Add to overall metadata
            all_metadata.update(model_info)
    
    print(f"Extracted metadata for {len(all_metadata)} models")
    return all_metadata

def extract_model_metadata():
    """Extract metadata from all models and save it to a file."""
    # Get model metadata
    metadata = get_all_model_metadata()
    
    if not metadata:
        print("No model metadata extracted. Exiting.")
        sys.exit(1)
    
    # Save metadata to a file
    output_dir = os.path.join(dashboard_dir, 'migrations', 'metadata')
    os.makedirs(output_dir, exist_ok=True)
    
    # Save as Python dictionary
    with open(os.path.join(output_dir, 'model_metadata.py'), 'w') as f:
        f.write('MODEL_METADATA = ')
        f.write(repr(metadata))
    
    # Also save as JSON for easier inspection
    with open(os.path.join(output_dir, 'model_metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Model metadata saved to {output_dir}/model_metadata.py")
    print(f"Found {len(metadata)} models")

if __name__ == '__main__':
    extract_model_metadata() 