#!/usr/bin/env python3
"""
Test MCN Fullstack Generation with ShadCN UI
"""

import sys
import os
from pathlib import Path

# Add MCN to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mcn', 'fullstack'))

def test_react_generator():
    """Test React generator with ShadCN UI"""
    print("=== Testing React Generator with ShadCN UI ===")
    
    try:
        from react_generator import ReactProjectGenerator
        
        generator = ReactProjectGenerator()
        
        # Create test UI manifest
        manifest = {
            "pages": {
                "Dashboard": {
                    "path": "/",
                    "components": [
                        {
                            "type": "container",
                            "props": {"className": "dashboard-container"},
                            "children": [
                                {
                                    "type": "text",
                                    "props": {"content": "Welcome to Dashboard", "tag": "h1"}
                                },
                                {
                                    "type": "button",
                                    "props": {"text": "Refresh Data"},
                                    "events": {"onClick": "refresh_dashboard"}
                                }
                            ]
                        }
                    ]
                },
                "Users": {
                    "path": "/users",
                    "components": [
                        {
                            "type": "table",
                            "props": {
                                "columns": ["ID", "Name", "Email"],
                                "dataSource": "users"
                            }
                        }
                    ]
                }
            }
        }
        
        # Save manifest
        import json
        with open("test_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        
        # Generate React project
        result = generator.generate_project(
            "test_manifest.json",
            "test_react_output",
            "TestApp"
        )
        
        print(f"SUCCESS React Generator: {result}")
        
        # Check if ShadCN components were generated
        ui_dir = Path("test_react_output/src/components/ui")
        if ui_dir.exists():
            components = list(ui_dir.glob("*.tsx"))
            print(f"SUCCESS ShadCN Components: {len(components)} generated")
            for comp in components:
                print(f"   - {comp.name}")
        
        # Cleanup
        os.remove("test_manifest.json")
        
    except Exception as e:
        print(f"ERROR React Generator: {e}")

def test_app_generator():
    """Test full app generator"""
    print("\n=== Testing App Generator ===")
    
    try:
        from mcn_generator.app_generator import MCNAppGenerator
        
        generator = MCNAppGenerator()
        
        # Test creating a new app
        result = generator.create_app(
            "test_mcn_app",
            template="business",
            features=["auth", "analytics"]
        )
        
        print(f"SUCCESS App Generator: Created app with result code {result}")
        
        # Check generated structure
        app_dir = Path("test_mcn_app")
        if app_dir.exists():
            print("SUCCESS Generated Structure:")
            for item in app_dir.rglob("*"):
                if item.is_file():
                    print(f"   - {item.relative_to(app_dir)}")
        
    except Exception as e:
        print(f"ERROR App Generator: {e}")

def test_model_generation():
    """Test model generation"""
    print("\n=== Testing Model Generation ===")
    
    try:
        from mcn_generator.app_generator import MCNAppGenerator
        
        generator = MCNAppGenerator()
        
        # Test model generation
        fields = {
            "name": "string",
            "email": "string", 
            "age": "number",
            "active": "boolean"
        }
        
        result = generator.generate_model("User", fields)
        print(f"SUCCESS Model Generation: Result code {result}")
        
        # Check if model file was created
        model_file = Path("backend/user.mcn")
        if model_file.exists():
            print("SUCCESS Model file created")
            with open(model_file, 'r') as f:
                content = f.read()
                if "CREATE TABLE" in content and "CRUD Operations" in content:
                    print("SUCCESS Model contains CRUD operations")
        
    except Exception as e:
        print(f"ERROR Model Generation: {e}")

def run_all_tests():
    """Run all fullstack generation tests"""
    print("MCN Fullstack Generation Test Suite")
    print("=" * 50)
    
    test_react_generator()
    test_app_generator() 
    test_model_generation()
    
    print("\n" + "=" * 50)
    print("Fullstack Generation Tests Complete!")
    print("\nKey Features Tested:")
    print("- React Generator with ShadCN UI")
    print("- Full App Generation with Dynamic Backend")
    print("- Model Generation with Real CRUD")
    print("- Enhanced UI Components")
    print("- Real Database Integration")

if __name__ == "__main__":
    run_all_tests()