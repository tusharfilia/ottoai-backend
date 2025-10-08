#!/usr/bin/env python3
"""
Scan for hardcoded secrets in the codebase.
This script should be run in CI to prevent secret leaks.
"""
import os
import re
import sys
from pathlib import Path

# Patterns that indicate potential secrets
SECRET_PATTERNS = [
    r'sk_live_[a-zA-Z0-9]{24,}',  # Stripe live keys
    r'sk_test_[a-zA-Z0-9]{24,}',  # Stripe test keys
    r'pk_live_[a-zA-Z0-9]{24,}',  # Stripe public keys
    r'pk_test_[a-zA-Z0-9]{24,}',  # Stripe test public keys
    r'sk-[a-zA-Z0-9]{48,}',       # OpenAI keys
    r'AKIA[0-9A-Z]{16}',          # AWS access keys
    r'[0-9a-f]{32}',              # MD5 hashes (potential secrets)
    r'[0-9a-f]{40}',              # SHA1 hashes (potential secrets)
    r'[0-9a-f]{64}',              # SHA256 hashes (potential secrets)
    r'password\s*=\s*["\'][^"\']+["\']',  # Password assignments
    r'secret\s*=\s*["\'][^"\']+["\']',    # Secret assignments
    r'token\s*=\s*["\'][^"\']+["\']',     # Token assignments
    r'api_key\s*=\s*["\'][^"\']+["\']',   # API key assignments
]

# Directories to exclude
EXCLUDE_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv',
    'migrations', 'tests', '.pytest_cache', 'coverage'
}

# File extensions to check
INCLUDE_EXTENSIONS = {'.py', '.js', '.ts', '.tsx', '.vue', '.json', '.yaml', '.yml'}

def should_scan_file(file_path: Path) -> bool:
    """Check if file should be scanned."""
    # Check if in excluded directory
    for part in file_path.parts:
        if part in EXCLUDE_DIRS:
            return False
    
    # Check file extension
    if file_path.suffix not in INCLUDE_EXTENSIONS:
        return False
    
    return True

def scan_file(file_path: Path) -> list:
    """Scan a single file for secrets."""
    findings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                for pattern in SECRET_PATTERNS:
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    for match in matches:
                        findings.append({
                            'file': str(file_path),
                            'line': line_num,
                            'pattern': pattern,
                            'match': match.group(),
                            'context': line.strip()
                        })
    
    except Exception as e:
        print(f"Error scanning {file_path}: {e}")
    
    return findings

def main():
    """Main scanning function."""
    print("Scanning for hardcoded secrets...")
    
    # Get the project root
    project_root = Path(__file__).parent.parent
    
    all_findings = []
    
    # Scan all relevant files
    for file_path in project_root.rglob('*'):
        if file_path.is_file() and should_scan_file(file_path):
            findings = scan_file(file_path)
            all_findings.extend(findings)
    
    # Report findings
    if all_findings:
        print(f"\n❌ Found {len(all_findings)} potential secrets:")
        for finding in all_findings:
            print(f"  {finding['file']}:{finding['line']} - {finding['pattern']}")
            print(f"    Match: {finding['match']}")
            print(f"    Context: {finding['context']}")
            print()
        
        print("❌ Secret scan FAILED")
        sys.exit(1)
    else:
        print("✅ No hardcoded secrets found")
        print("✅ Secret scan PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
