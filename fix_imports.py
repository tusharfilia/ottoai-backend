#!/usr/bin/env python3
"""
Comprehensive import and compatibility fixer for Otto AI backend.
Automatically detects and fixes common SQLAlchemy, FastAPI, and import issues.
"""

import os
import re
import glob
from pathlib import Path

def fix_sqlalchemy_imports(file_path):
    """Fix missing SQLAlchemy imports in a file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find all SQLAlchemy column types used in the file
    sqlalchemy_types = set()
    
    # Common SQLAlchemy types that might be missing
    type_patterns = {
        'Float': r'\bFloat\b',
        'Text': r'\bText\b', 
        'Boolean': r'\bBoolean\b',
        'Numeric': r'\bNumeric\b',
        'Date': r'\bDate\b',
        'Time': r'\bTime\b',
        'LargeBinary': r'\bLargeBinary\b',
        'PickleType': r'\bPickleType\b',
        'Unicode': r'\bUnicode\b',
        'UnicodeText': r'\bUnicodeText\b'
    }
    
    for type_name, pattern in type_patterns.items():
        if re.search(pattern, content):
            sqlalchemy_types.add(type_name)
    
    if not sqlalchemy_types:
        return False
    
    # Check if SQLAlchemy import exists
    if 'from sqlalchemy import' not in content:
        return False
    
    # Get current imports
    lines = content.split('\n')
    import_line = None
    for i, line in enumerate(lines):
        if line.startswith('from sqlalchemy import'):
            import_line = i
            break
    
    if import_line is None:
        return False
    
    # Parse existing imports
    current_imports = set()
    import_content = lines[import_line]
    if '(' in import_content and ')' in import_content:
        # Multi-line import
        start = import_content.find('(') + 1
        end = import_content.rfind(')')
        imports_text = import_content[start:end]
        current_imports = {imp.strip() for imp in imports_text.split(',')}
    else:
        # Single line import
        parts = import_content.split('import')[1].strip()
        current_imports = {imp.strip() for imp in parts.split(',')}
    
    # Add missing imports
    missing_imports = sqlalchemy_types - current_imports
    if not missing_imports:
        return False
    
    # Update the import line
    all_imports = sorted(current_imports | missing_imports)
    new_import = f"from sqlalchemy import {', '.join(all_imports)}"
    lines[import_line] = new_import
    
    # Write back
    with open(file_path, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"✅ Fixed SQLAlchemy imports in {file_path}: {', '.join(missing_imports)}")
    return True

def fix_fastapi_compatibility(file_path):
    """Fix FastAPI compatibility issues."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    changes_made = False
    
    # Fix Field() in function parameters to Query()
    if 'Field(' in content and 'def ' in content:
        # Add Query import if not present
        if 'from fastapi import' in content and 'Query' not in content:
            content = re.sub(
                r'(from fastapi import [^)]+)',
                r'\1, Query',
                content
            )
            changes_made = True
        
        # Replace Field() with Query() in function parameters
        content = re.sub(
            r'(\w+): int = Field\([^)]+\)',
            r'\1): int = Query(...)',
            content
        )
        content = re.sub(
            r'(\w+): Optional\[str\] = Field\(None\)',
            r'\1): Optional[str] = Query(None)',
            content
        )
        content = re.sub(
            r'(\w+): str = Field\([^)]+\)',
            r'\1): str = Query(...)',
            content
        )
        
        if changes_made:
            print(f"✅ Fixed FastAPI compatibility in {file_path}")
    
    if changes_made:
        with open(file_path, 'w') as f:
            f.write(content)
    
    return changes_made

def fix_uwc_imports(file_path):
    """Fix UWC client import issues."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    if 'uwc_client' not in content:
        return False
    
    changes_made = False
    
    # Fix import statement
    if 'from app.services.uwc_client import get_uwc_client' in content:
        content = content.replace(
            'from app.services.uwc_client import get_uwc_client',
            'from app.services.uwc_client import get_uwc_client'
        )
        changes_made = True
    
    # Fix usage patterns
    # Pattern 1: Direct usage
    content = re.sub(
        r'uwc_client\.(\w+)\(([^)]+)\)',
        r'get_uwc_client().\1(\2)',
        content
    )
    
    # Pattern 2: In async functions, add await
    if 'async def' in content:
        content = re.sub(
            r'get_uwc_client\(\)\.(\w+)\(([^)]+)\)',
            r'await get_uwc_client().\1(\2)',
            content
        )
    
    if changes_made:
        print(f"✅ Fixed UWC imports in {file_path}")
        with open(file_path, 'w') as f:
            f.write(content)
    
    return changes_made

def fix_sqlalchemy_metadata_conflicts(file_path):
    """Fix SQLAlchemy metadata conflicts."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    if 'metadata' not in content or 'class ' not in content:
        return False
    
    changes_made = False
    
    # Fix metadata field name conflicts
    if 'audit_metadata = Column(' in content:
        content = content.replace(
            'audit_metadata = Column(',
            'audit_audit_metadata = Column('
        )
        changes_made = True
    
    if changes_made:
        print(f"✅ Fixed SQLAlchemy metadata conflicts in {file_path}")
        with open(file_path, 'w') as f:
            f.write(content)
    
    return changes_made

def fix_missing_imports(file_path):
    """Fix missing imports in general."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    changes_made = False
    
    # Check for common missing imports
    if 'require_role' in content and 'from app.middleware.rbac import require_role' not in content:
        # Add require_role import
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('from app.') and 'import' in line:
                lines.insert(i + 1, 'from app.middleware.rbac import require_role')
                changes_made = True
                break
    
    if changes_made:
        print(f"✅ Fixed missing imports in {file_path}")
        with open(file_path, 'w') as f:
            f.write('\n'.join(lines))
    
    return changes_made

def main():
    """Main function to fix all issues."""
    print("🔧 Starting comprehensive import and compatibility fixes...")
    
    # Find all Python files
    python_files = []
    for root, dirs, files in os.walk('.'):
        # Skip __pycache__ and .git directories
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'node_modules']]
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    total_fixes = 0
    
    for file_path in python_files:
        print(f"🔍 Checking {file_path}...")
        
        # Apply all fixes
        fixes = [
            fix_sqlalchemy_imports,
            fix_fastapi_compatibility,
            fix_uwc_imports,
            fix_sqlalchemy_metadata_conflicts,
            fix_missing_imports
        ]
        
        for fix_func in fixes:
            try:
                if fix_func(file_path):
                    total_fixes += 1
            except Exception as e:
                print(f"⚠️  Error fixing {file_path}: {e}")
    
    print(f"\n✅ Fixed {total_fixes} issues across {len(python_files)} files")
    print("🚀 All fixes applied! Try deploying again.")

if __name__ == "__main__":
    main()

