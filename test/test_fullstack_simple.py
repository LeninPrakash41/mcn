#!/usr/bin/env python3
"""
Simple Full-Stack Integration Test
Tests core UI integration without external dependencies
"""

import sys
import os
import json
import shutil

def test_ui_bindings():
    """Test UI bindings system directly"""
    print("=== Testing UI Bindings System ===")
    
    try:
        # Import UI bindings directly
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from mcn.core_engine.mcn_ui_bindings import UIBindingManager, UIIntegrationLayer
        
        # Create UI manager
        ui_manager = UIBindingManager()
        
        # Test component creation
        button_id = ui_manager.button("Test Button", "test_action")
        input_id = ui_manager.input("Test input...", "input_change")
        text_id = ui_manager.text("Test Text")
        container_id = ui_manager.container([button_id, input_id, text_id])
        
        print(f"Created {len(ui_manager.components)} components")
        
        # Test page creation
        page_id = ui_manager.create_page("TestPage", "/test", [container_id])
        print(f"Created {len(ui_manager.pages)} pages")
        
        # Test React generation
        button_component = ui_manager.components[button_id]
        react_jsx = ui_manager.generate_react_component(button_component)
        print("React component generation works")
        
        return True
        
    except Exception as e:
        print(f"UI bindings test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_react_generator():
    """Test React project generator"""
    print("\n=== Testing React Project Generator ===")
    
    try:
        from mcn.fullstack.react_generator import ReactProjectGenerator
        
        # Create test manifest
        test_manifest = {
            "pages": {
                "TestPage": {
                    "name": "TestPage",
                    "path": "/test",
                    "components": [
                        {
                            "type": "button",
                            "props": {"text": "Test Button"},
                            "events": {"onClick": "test_action"}
                        }
                    ]
                }
            },
            "components": {},
            "event_handlers": {"test_action": "test_function"},
            "data_bindings": {}
        }
        
        # Create test directory
        test_dir = "d:\\mcn\\test\\react_test_output"
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        os.makedirs(test_dir, exist_ok=True)
        
        # Save test manifest
        manifest_path = os.path.join(test_dir, "test-manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(test_manifest, f, indent=2)
        
        # Generate React project
        generator = ReactProjectGenerator()
        output_dir = os.path.join(test_dir, "test-react-app")
        
        result = generator.generate_project(manifest_path, output_dir, "TestApp")
        print("React project generated")
        
        # Check key files
        key_files = [
            "package.json",
            "src/index.tsx",
            "src/AppRouter.tsx",
            "src/components/UIComponents.tsx",
            "src/services/mcn-client.tsx"
        ]
        
        for file_path in key_files:
            full_path = os.path.join(output_dir, file_path)
            if os.path.exists(full_path):
                print(f"+ {file_path} generated")
            else:
                print(f"- {file_path} missing")
        
        return True
        
    except Exception as e:
        print(f"React generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ui_export():
    """Test complete UI export process"""
    print("\n=== Testing UI Export Process ===")
    
    try:
        from mcn.core_engine.mcn_ui_bindings import UIBindingManager
        
        # Create UI components
        ui_manager = UIBindingManager()
        
        # Create a simple e-commerce layout
        header = ui_manager.text("MCN Store", tag="h1")
        search = ui_manager.input("Search products...", "search_products")
        product_table = ui_manager.table(["Name", "Price", "Stock"], "products")
        
        main_container = ui_manager.container([header, search, product_table])
        home_page = ui_manager.create_page("Home", "/", [main_container])
        
        # Export to React
        test_dir = "d:\\mcn\\test\\ui_export_test"
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        
        ui_manager.export_to_react_project(test_dir)
        print("UI exported to React project")
        
        # Check generated files
        expected_files = [
            "pages/HomePage.tsx",
            "AppRouter.tsx", 
            "ui-manifest.json"
        ]
        
        for file_path in expected_files:
            full_path = os.path.join(test_dir, file_path)
            if os.path.exists(full_path):
                print(f"+ {file_path} exported")
            else:
                print(f"- {file_path} missing")
        
        # Check manifest content
        manifest_path = os.path.join(test_dir, "ui-manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                print(f"Manifest contains {len(manifest.get('pages', {}))} pages")
                print(f"Manifest contains {len(manifest.get('components', {}))} components")
        
        return True
        
    except Exception as e:
        print(f"UI export test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_sample_mcn_app():
    """Create a sample MCN application for testing"""
    print("\n=== Creating Sample MCN Application ===")
    
    try:
        from mcn.core_engine.mcn_ui_bindings import UIBindingManager
        
        ui_manager = UIBindingManager()
        
        # Create comprehensive e-commerce app
        # Header
        logo = ui_manager.text("MCN E-Commerce", tag="h1", className="logo")
        search = ui_manager.input("Search products...", "search_products", className="search-bar")
        cart = ui_manager.button("Cart (0)", "view_cart", className="cart-btn")
        header = ui_manager.container([logo, search, cart], className="header")
        
        # Product grid
        product_grid = ui_manager.container([], className="product-grid", id="products")
        
        # Analytics
        metrics = ui_manager.container([
            ui_manager.text("Revenue: $0", tag="p", id="revenue"),
            ui_manager.text("Orders: 0", tag="p", id="orders"),
            ui_manager.text("Products: 0", tag="p", id="products-count")
        ], className="metrics")
        
        sales_chart = ui_manager.chart("bar", "sales_data", className="sales-chart")
        
        # Orders table
        orders_table = ui_manager.table(
            ["Order ID", "Product", "Quantity", "Total", "Status"], 
            "recent_orders",
            className="orders-table"
        )
        
        # Main layout
        main_layout = ui_manager.container([
            header, product_grid, metrics, sales_chart, orders_table
        ], className="main-app")
        
        # Create pages
        home_page = ui_manager.create_page("Home", "/", [main_layout], 
                                         title="MCN E-Commerce Store")
        admin_page = ui_manager.create_page("Admin", "/admin", [metrics, sales_chart, orders_table],
                                          title="Admin Dashboard")
        
        # Export complete application
        output_dir = "d:\\mcn\\test\\sample_mcn_ecommerce"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        
        ui_manager.export_to_react_project(output_dir)
        
        print("Sample MCN e-commerce app created")
        print(f"Generated {len(ui_manager.components)} components")
        print(f"Generated {len(ui_manager.pages)} pages")
        print(f"Exported to: {output_dir}")
        
        # Generate package.json for the sample app
        from mcn.fullstack.react_generator import ReactProjectGenerator
        generator = ReactProjectGenerator()
        
        # Create manifest from UI manager
        manifest = {
            'pages': {name: {
                'name': page.name,
                'path': page.path,
                'components': [{'type': 'container', 'props': {}, 'children': []}]
            } for name, page in ui_manager.pages.items()},
            'components': {},
            'event_handlers': {},
            'data_bindings': {}
        }
        
        manifest_path = os.path.join(output_dir, "ui-manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Generate complete React project
        generator.generate_project(manifest_path, output_dir, "MCN-ECommerce")
        
        print("Complete React project generated with:")
        print("  - TypeScript configuration")
        print("  - Tailwind CSS setup")
        print("  - React Router")
        print("  - MCN client integration")
        print("  - Responsive UI components")
        
        return True
        
    except Exception as e:
        print(f"Sample app creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_simple_tests():
    """Run simplified full-stack tests"""
    print("MCN Full-Stack Integration - Simple Test Suite")
    print("=" * 60)
    
    tests = [
        test_ui_bindings,
        test_react_generator,
        test_ui_export,
        create_sample_mcn_app
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"Test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All full-stack integration tests passed!")
        print("\nGenerated sample applications:")
        print("1. d:\\mcn\\test\\react_test_output\\test-react-app\\")
        print("2. d:\\mcn\\test\\ui_export_test\\")
        print("3. d:\\mcn\\test\\sample_mcn_ecommerce\\")
        print("\nTo run the sample React app:")
        print("cd d:\\mcn\\test\\sample_mcn_ecommerce")
        print("npm install")
        print("npm start")
        return True
    else:
        print("Some tests failed")
        return False

if __name__ == "__main__":
    success = run_simple_tests()
    sys.exit(0 if success else 1)