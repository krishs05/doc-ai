#!/usr/bin/env python3
"""
Environment Setup Script for Doc-AI Hospital Management System
This script helps you set up the required environment variables.
"""

import os
import sys
from pathlib import Path

def create_env_file():
    """Create a .env file with the required environment variables"""
    
    env_content = """# Database Configuration
DB_HOST=localhost
DB_NAME=hospital
DB_USER=postgres
DB_PASSWORD=postgres
DB_PORT=5432

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key

# Flask Configuration
FLASK_DEBUG=False
"""
    
    env_file = Path('.env')
    
    if env_file.exists():
        print("⚠️  .env file already exists!")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ .env file created successfully!")
        print("\n📝 Next steps:")
        print("1. Edit the .env file and add your AWS credentials")
        print("2. Make sure your database and Redis are running")
        print("3. Run 'python main.py' to start the application")
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")

def check_requirements():
    """Check if required packages are installed"""
    required_packages = [
        'flask',
        'psycopg2-binary',
        'boto3',
        'langchain-aws',
        'sentence-transformers',
        'faiss-cpu'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n💡 Install missing packages with:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    else:
        print("✅ All required packages are installed!")
        return True

def main():
    """Main setup function"""
    print("🏥 Doc-AI Hospital Management System Setup")
    print("=" * 50)
    
    # Check requirements
    print("\n📦 Checking requirements...")
    if not check_requirements():
        return
    
    # Create .env file
    print("\n🔧 Setting up environment...")
    create_env_file()
    
    print("\n🎉 Setup complete!")
    print("\n📚 For more information, see the README.md file")

if __name__ == "__main__":
    main() 