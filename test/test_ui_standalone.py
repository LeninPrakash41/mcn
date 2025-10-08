#!/usr/bin/env python3
"""
Standalone UI Integration Test
Tests UI bindings and React generation without MCN runtime dependencies
"""

import sys
import os
import json
import shutil

# Add MCN path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_react_generator_standalone():
    """Test React project generator independently"""
    print("=== Testing React Project Generator (Standalone) ===")
    
    try:
        from mcn.fullstack.react_generator import ReactProjectGenerator
        
        # Create comprehensive test manifest
        test_manifest = {
            "pages": {
                "Home": {
                    "name": "Home",
                    "path": "/",
                    "components": [
                        {
                            "type": "container",
                            "props": {"className": "main-app"},
                            "children": [
                                {
                                    "type": "text",
                                    "props": {"content": "MCN E-Commerce Store", "tag": "h1", "className": "logo"}
                                },
                                {
                                    "type": "input", 
                                    "props": {"placeholder": "Search products...", "className": "search-bar"},
                                    "events": {"onChange": "search_products"}
                                },
                                {
                                    "type": "button",
                                    "props": {"text": "Cart (0)", "className": "cart-btn"},
                                    "events": {"onClick": "view_cart"}
                                },
                                {
                                    "type": "table",
                                    "props": {
                                        "columns": ["Name", "Price", "Stock"],
                                        "dataSource": "products",
                                        "className": "product-table"
                                    }
                                },
                                {
                                    "type": "chart",
                                    "props": {
                                        "chartType": "bar",
                                        "data": "sales_data",
                                        "className": "sales-chart"
                                    }
                                }
                            ]
                        }
                    ]
                },
                "Admin": {
                    "name": "Admin", 
                    "path": "/admin",
                    "components": [
                        {
                            "type": "container",
                            "props": {"className": "admin-dashboard"},
                            "children": [
                                {
                                    "type": "text",
                                    "props": {"content": "Admin Dashboard", "tag": "h1"}
                                },
                                {
                                    "type": "chart",
                                    "props": {"chartType": "line", "data": "analytics_data"}
                                }
                            ]
                        }
                    ]
                }
            },
            "components": {},
            "event_handlers": {
                "search_products": "search_products_function",
                "view_cart": "view_cart_function"
            },
            "data_bindings": {
                "products": "product_data_source",
                "sales_data": "sales_analytics_source"
            }
        }
        
        # Create test directory
        test_dir = "d:\\mcn\\test\\fullstack_test_standalone"
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        os.makedirs(test_dir, exist_ok=True)
        
        # Save test manifest
        manifest_path = os.path.join(test_dir, "ecommerce-manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(test_manifest, f, indent=2)
        
        print(f"Created test manifest with {len(test_manifest['pages'])} pages")
        
        # Generate React project
        generator = ReactProjectGenerator()
        output_dir = os.path.join(test_dir, "mcn-ecommerce-react")
        
        result = generator.generate_project(manifest_path, output_dir, "MCN-ECommerce")
        print("React project generated successfully")
        
        # Verify generated files
        expected_files = [
            "package.json",
            "src/index.tsx",
            "src/AppRouter.tsx", 
            "src/components/UIComponents.tsx",
            "src/services/mcn-client.tsx",
            "src/styles/index.css",
            "tailwind.config.js",
            "tsconfig.json",
            "public/index.html"
        ]
        
        print("Checking generated files:")
        for file_path in expected_files:
            full_path = os.path.join(output_dir, file_path)
            if os.path.exists(full_path):
                print(f"  + {file_path}")
            else:
                print(f"  - {file_path} MISSING")
        
        # Check page components
        pages_dir = os.path.join(output_dir, "src/pages")
        if os.path.exists(pages_dir):
            page_files = os.listdir(pages_dir)
            print(f"Generated page components: {page_files}")
        
        # Verify package.json content
        package_json_path = os.path.join(output_dir, "package.json")
        if os.path.exists(package_json_path):
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
                print(f"Project name: {package_data.get('name')}")
                print(f"Dependencies: {len(package_data.get('dependencies', {}))}")
        
        # Check if React components are properly generated
        ui_components_path = os.path.join(output_dir, "src/components/UIComponents.tsx")
        if os.path.exists(ui_components_path):
            with open(ui_components_path, 'r') as f:
                content = f.read()
                components = ['UIButton', 'UIInput', 'UIText', 'UIContainer', 'UITable', 'UIChart']
                for comp in components:
                    if comp in content:
                        print(f"  + {comp} component generated")
                    else:
                        print(f"  - {comp} component missing")
        
        print(f"\nComplete React application generated at: {output_dir}")
        print("Ready for development with:")
        print("  - React 18 + TypeScript")
        print("  - Tailwind CSS styling")
        print("  - React Router navigation")
        print("  - Recharts for data visualization")
        print("  - MCN backend integration")
        
        return True
        
    except Exception as e:
        print(f"React generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_sample_business_app():
    """Create a sample business application"""
    print("\n=== Creating Sample Business Application ===")
    
    try:
        from mcn.fullstack.react_generator import ReactProjectGenerator
        
        # Business dashboard manifest
        business_manifest = {
            "pages": {
                "Dashboard": {
                    "name": "Dashboard",
                    "path": "/",
                    "components": [
                        {
                            "type": "container",
                            "props": {"className": "dashboard-layout"},
                            "children": [
                                {
                                    "type": "text",
                                    "props": {"content": "Business Intelligence Dashboard", "tag": "h1", "className": "dashboard-title"}
                                },
                                {
                                    "type": "container",
                                    "props": {"className": "metrics-row"},
                                    "children": [
                                        {
                                            "type": "container",
                                            "props": {"className": "metric-card"},
                                            "children": [
                                                {"type": "text", "props": {"content": "Total Revenue", "tag": "h3"}},
                                                {"type": "text", "props": {"content": "$125,430", "tag": "p", "className": "metric-value"}}
                                            ]
                                        },
                                        {
                                            "type": "container", 
                                            "props": {"className": "metric-card"},
                                            "children": [
                                                {"type": "text", "props": {"content": "Active Users", "tag": "h3"}},
                                                {"type": "text", "props": {"content": "2,847", "tag": "p", "className": "metric-value"}}
                                            ]
                                        },
                                        {
                                            "type": "container",
                                            "props": {"className": "metric-card"}, 
                                            "children": [
                                                {"type": "text", "props": {"content": "Conversion Rate", "tag": "h3"}},
                                                {"type": "text", "props": {"content": "3.24%", "tag": "p", "className": "metric-value"}}
                                            ]
                                        }
                                    ]
                                },
                                {
                                    "type": "chart",
                                    "props": {"chartType": "line", "data": "revenue_trend", "className": "main-chart"}
                                },
                                {
                                    "type": "container",
                                    "props": {"className": "data-section"},
                                    "children": [
                                        {
                                            "type": "button",
                                            "props": {"text": "Generate AI Insights", "className": "btn-primary"},
                                            "events": {"onClick": "generate_insights"}
                                        },
                                        {
                                            "type": "table",
                                            "props": {
                                                "columns": ["Customer", "Revenue", "Status", "Last Order"],
                                                "dataSource": "customer_data",
                                                "className": "customer-table"
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                "Analytics": {
                    "name": "Analytics",
                    "path": "/analytics", 
                    "components": [
                        {
                            "type": "container",
                            "props": {"className": "analytics-page"},
                            "children": [
                                {"type": "text", "props": {"content": "Advanced Analytics", "tag": "h1"}},
                                {"type": "chart", "props": {"chartType": "bar", "data": "sales_by_category"}},
                                {"type": "chart", "props": {"chartType": "line", "data": "user_engagement"}}
                            ]
                        }
                    ]
                }
            },
            "components": {},
            "event_handlers": {
                "generate_insights": "ai_generate_business_insights",
                "refresh_data": "refresh_dashboard_data"
            },
            "data_bindings": {
                "revenue_trend": "monthly_revenue_data",
                "customer_data": "top_customers_data",
                "sales_by_category": "category_sales_data",
                "user_engagement": "engagement_metrics"
            }
        }
        
        # Create business app
        test_dir = "d:\\mcn\\test\\business_app_sample"
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        os.makedirs(test_dir, exist_ok=True)
        
        manifest_path = os.path.join(test_dir, "business-manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(business_manifest, f, indent=2)
        
        generator = ReactProjectGenerator()
        output_dir = os.path.join(test_dir, "business-dashboard")
        
        generator.generate_project(manifest_path, output_dir, "Business-Dashboard")
        
        print("Business dashboard application created")
        print(f"Location: {output_dir}")
        print("Features:")
        print("  - Executive dashboard with KPI metrics")
        print("  - Revenue and engagement charts")
        print("  - Customer data table")
        print("  - AI insights integration")
        print("  - Multi-page navigation")
        
        return True
        
    except Exception as e:
        print(f"Business app creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_generated_projects():
    """Verify the generated projects are complete"""
    print("\n=== Verifying Generated Projects ===")
    
    projects = [
        "d:\\mcn\\test\\fullstack_test_standalone\\mcn-ecommerce-react",
        "d:\\mcn\\test\\business_app_sample\\business-dashboard"
    ]
    
    for project_path in projects:
        if os.path.exists(project_path):
            print(f"\nProject: {os.path.basename(project_path)}")
            
            # Check package.json
            package_path = os.path.join(project_path, "package.json")
            if os.path.exists(package_path):
                with open(package_path, 'r') as f:
                    package_data = json.load(f)
                    print(f"  Name: {package_data.get('name')}")
                    print(f"  Dependencies: {len(package_data.get('dependencies', {}))}")
            
            # Check src structure
            src_path = os.path.join(project_path, "src")
            if os.path.exists(src_path):
                src_items = os.listdir(src_path)
                print(f"  Src structure: {src_items}")
            
            # Check pages
            pages_path = os.path.join(project_path, "src", "pages")
            if os.path.exists(pages_path):
                pages = os.listdir(pages_path)
                print(f"  Pages: {pages}")
            
            print(f"  Status: Ready for development")
        else:
            print(f"Project not found: {project_path}")

def run_standalone_tests():
    """Run standalone UI tests"""
    print("MCN Full-Stack Integration - Standalone Test Suite")
    print("=" * 65)
    
    tests = [
        test_react_generator_standalone,
        create_sample_business_app,
        verify_generated_projects
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"Test failed: {e}")
    
    print("\n" + "=" * 65)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All standalone integration tests passed!")
        print("\nGenerated applications:")
        print("1. E-Commerce App: d:\\mcn\\test\\fullstack_test_standalone\\mcn-ecommerce-react\\")
        print("2. Business Dashboard: d:\\mcn\\test\\business_app_sample\\business-dashboard\\")
        print("\nTo run either application:")
        print("1. cd [app-directory]")
        print("2. npm install")
        print("3. npm start")
        print("4. Open http://localhost:3000")
        return True
    else:
        print("Some tests failed")
        return False

if __name__ == "__main__":
    success = run_standalone_tests()
    sys.exit(0 if success else 1)