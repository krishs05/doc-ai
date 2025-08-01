#!/usr/bin/env python3
"""
Doc-AI System Health Check
This script verifies that all dependencies and components are properly configured.
"""

import sys
import os
import importlib
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.8+"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Requires Python 3.8+")
        return False

def check_required_packages():
    """Check if all required Python packages are installed"""
    print("\n📦 Checking Python packages...")
    
    required_packages = [
        'flask',
        'flask_cors',
        'psycopg2',
        'boto3',
        'python-dotenv',
        'requests'
    ]
    
    optional_packages = [
        'sentence_transformers',
        'faiss',
        'langchain_aws',
        'langchain_core',
        'pydantic'
    ]
    
    all_good = True
    
    for package in required_packages:
        try:
            importlib.import_module(package.replace('-', '_'))
            print(f"✅ {package} - Installed")
        except ImportError:
            print(f"❌ {package} - Missing")
            all_good = False
    
    print("\n🔧 Checking optional packages...")
    for package in optional_packages:
        try:
            importlib.import_module(package.replace('-', '_'))
            print(f"✅ {package} - Installed")
        except ImportError:
            print(f"⚠️  {package} - Not installed (optional)")
    
    return all_good

def check_environment_file():
    """Check if .env file exists and has required variables"""
    print("\n🔐 Checking environment configuration...")
    
    env_path = Path('.env')
    if not env_path.exists():
        print("❌ .env file not found")
        print("📝 Create .env file with database and AWS credentials")
        return False
    
    required_vars = [
        'DB_HOST',
        'DB_NAME',
        'DB_USER',
        'DB_PASSWORD',
        'AWS_REGION'
    ]
    
    missing_vars = []
    
    try:
        with open('.env', 'r') as f:
            content = f.read()
            for var in required_vars:
                if f"{var}=" not in content or f"{var}=\n" in content:
                    missing_vars.append(var)
        
        if missing_vars:
            print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
            return False
        else:
            print("✅ .env file configured")
            return True
            
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False

def check_database_connection():
    """Test database connection"""
    print("\n🗄️  Checking database connection...")
    
    try:
        import psycopg2
        from dotenv import load_dotenv
        
        load_dotenv()
        
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            port=os.getenv('DB_PORT', 5432)
        )
        
        with conn.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"✅ Database connected - {version[:50]}...")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("💡 Make sure PostgreSQL is running and credentials are correct")
        return False

def check_aws_credentials():
    """Check AWS credentials and Bedrock access"""
    print("\n☁️  Checking AWS configuration...")
    
    try:
        import boto3
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Test basic AWS credentials
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ AWS credentials valid - Account: {identity['Account']}")
        
        # Test Bedrock access
        bedrock = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        print("✅ Bedrock client initialized")
        
        return True
        
    except Exception as e:
        print(f"❌ AWS configuration failed: {e}")
        print("💡 Check AWS credentials and Bedrock model access")
        return False

def check_frontend_setup():
    """Check frontend dependencies"""
    print("\n🌐 Checking frontend setup...")
    
    frontend_path = Path('frontend')
    if not frontend_path.exists():
        print("❌ Frontend directory not found")
        return False
    
    package_json = frontend_path / 'package.json'
    if not package_json.exists():
        print("❌ Frontend package.json not found")
        return False
    
    node_modules = frontend_path / 'node_modules'
    if not node_modules.exists():
        print("⚠️  Frontend dependencies not installed")
        print("💡 Run: cd frontend && npm install")
        return False
    
    print("✅ Frontend setup complete")
    return True

def check_project_structure():
    """Verify project structure"""
    print("\n📁 Checking project structure...")
    
    required_files = [
        'main.py',
        'requirements.txt',
        'schema.sql',
        'setup_database.py',
        'frontend/public/index.html',
        'frontend/public/app.js',
        'frontend/public/chat.js',
        'frontend/public/style.css',
        'frontend/public/chat-styles.css'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {', '.join(missing_files)}")
        return False
    else:
        print("✅ Project structure complete")
        return True

def main():
    """Run all health checks"""
    print("🏥 Doc-AI System Health Check")
    print("=" * 50)
    
    checks = [
        check_python_version,
        check_required_packages,
        check_project_structure,
        check_environment_file,
        check_database_connection,
        check_aws_credentials,
        check_frontend_setup
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"❌ Check failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 Summary:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 All checks passed! ({passed}/{total})")
        print("\n🚀 You can now start the application:")
        print("   Backend:  python3 main.py")
        print("   Frontend: cd frontend && npm start")
    else:
        print(f"⚠️  {passed}/{total} checks passed")
        print("\n🔧 Please fix the issues above before running the application")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)