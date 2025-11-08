#!/usr/bin/env python3
"""
Test script to validate the new models can be imported without errors.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_app
    from app.models.storage import StorageFile, FileVersion, Lock, AuditLog
    from app.config import DevelopmentConfig

    print("✅ All models imported successfully")

    # Test basic model instantiation
    app = create_app(DevelopmentConfig)
    with app.app_context():
        print("✅ App context created successfully")

        # Test basic model attributes
        print(f"✅ StorageFile table: {StorageFile.__tablename__}")
        print(f"✅ FileVersion table: {FileVersion.__tablename__}")
        print(f"✅ Lock table: {Lock.__tablename__}")
        print(f"✅ AuditLog table: {AuditLog.__tablename__}")

        print("✅ All models validated successfully!")

except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
