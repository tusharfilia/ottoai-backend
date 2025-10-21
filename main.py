#!/usr/bin/env python3
"""
Otto AI Backend - Main Entry Point
This file helps Railway detect this as a Python project.
The actual FastAPI app is in services/dashboard/app/main.py
"""

import sys
import os
import subprocess

def main():
    """Main entry point for Railway deployment"""
    print("🚀 Starting Otto AI Backend...")
    
    # Change to the dashboard directory
    dashboard_dir = os.path.join(os.path.dirname(__file__), 'services', 'dashboard')
    os.chdir(dashboard_dir)
    
    # Start the FastAPI server
    cmd = [
        sys.executable, '-m', 'uvicorn', 
        'app.main:app', 
        '--host', '0.0.0.0', 
        '--port', os.getenv('PORT', '8080')
    ]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd)

if __name__ == '__main__':
    main()
