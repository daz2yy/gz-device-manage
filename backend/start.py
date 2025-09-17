#!/usr/bin/env python3
"""
Device Management System Startup Script
"""
import sys
import subprocess
import os
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import fastapi
        import sqlalchemy
        import uvicorn
        print("✓ All Python dependencies are installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("Please install dependencies: pip install -r requirements.txt")
        return False

def check_external_tools():
    """Check if external tools are available."""
    tools = ['adb']
    missing = []
    
    for tool in tools:
        try:
            subprocess.run([tool, '--version'], capture_output=True, check=True)
            print(f"✓ {tool} is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"✗ {tool} is not available")
            missing.append(tool)
    
    if missing:
        print(f"\nMissing tools: {', '.join(missing)}")
        print("Please install missing tools:")
        print("- ADB: Install Android SDK Platform Tools")
        return False
    
    return True

def create_default_admin():
    """Create default admin user if none exists."""
    try:
        from database import SessionLocal, User as DBUser
        from auth import get_password_hash
        
        db = SessionLocal()
        
        # Check if admin user exists
        admin = db.query(DBUser).filter(DBUser.role == "admin").first()
        if not admin:
            # Create default admin
            admin_user = DBUser(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("✓ Created default admin user (username: admin, password: admin123)")
        else:
            print("✓ Admin user already exists")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ Failed to create admin user: {e}")
        return False

def main():
    """Main startup function."""
    print("🚀 Starting Device Management System...")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check external tools
    if not check_external_tools():
        print("\n⚠️  Some external tools are missing. The system will start but some features may not work.")
    
    # Initialize database and create admin user
    print("\n📊 Initializing database...")
    if not create_default_admin():
        print("⚠️  Failed to create admin user, but continuing...")
    
    print("\n🌐 Starting web server...")
    print("Access the system at: http://localhost:8001")
    print("Default admin credentials: admin / admin123")
    print("=" * 50)
    
    # Start the server
    try:
        import uvicorn
        uvicorn.run("main_enhanced:app", host="0.0.0.0", port=8001, reload=True)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"\n❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()