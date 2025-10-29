#!/usr/bin/env python3
"""
MCN Runner Script - Handles direct execution without import issues
"""

import sys
import os
import argparse


def main():
    """Simple MCN runner that handles basic commands"""
    global script_dir
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    parser = argparse.ArgumentParser(
        description="MCN (Macincode Scripting Language) Runner"
    )
    parser.add_argument(
        "command", nargs="?", default="repl", help="Command to run (run, repl, serve, postman, docs, codegen, monitor)"
    )
    parser.add_argument("file", nargs="?", help="MCN file to run")
    parser.add_argument("--port", type=int, default=8000, help="Port for serve command")
    parser.add_argument("--host", default="127.0.0.1", help="Host for serve command")

    args = parser.parse_args()

    # Add paths for imports
    mcn_lang_path = os.path.join(script_dir, "mcn")
    core_engine_path = os.path.join(mcn_lang_path, "core_engine")

    sys.path.insert(0, script_dir)
    sys.path.insert(0, mcn_lang_path)
    sys.path.insert(0, core_engine_path)

    if args.command == "run" and args.file:
        return run_file(args.file)
    elif args.command == "repl":
        return run_repl()
    elif args.command == "serve":
        print(f"Serve command not yet implemented")
        return 1
    elif args.command == "postman":
        return generate_postman_collection(args.file or "postman_exports")
    elif args.command == "docs":
        return generate_api_docs(args.file or "api_docs")
    elif args.command == "codegen":
        return generate_client_sdks(args.file or "generated_clients")
    elif args.command == "monitor":
        return show_monitoring_dashboard()
    else:
        parser.print_help()
        return 1


def run_file(filepath):
    """Run a MCN file using the real interpreter"""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found")
        return 1

    try:
        # Import the real MCN interpreter
        sys.path.insert(0, os.path.join(script_dir, "mcn", "core_engine"))
        from mcn_interpreter import MCNInterpreter
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"Running MCN file: {filepath}")
        
        # Use real interpreter
        interpreter = MCNInterpreter()
        result = interpreter.execute(content, filepath, quiet=False)
        
        if result is not None:
            print(f"Script result: {result}")
        
        return 0

    except Exception as e:
        print(f"Error running file: {e}")
        return 1


def run_repl():
    """Run MCN REPL with real interpreter"""
    print("MCN (Macincode Scripting Language) REPL v3.0 - Dynamic Systems")
    print("Type 'exit' to quit, 'help' for commands")
    print("-" * 40)
    
    try:
        # Import the real MCN interpreter
        sys.path.insert(0, os.path.join(script_dir, "mcn", "core_engine"))
        from mcn_interpreter import MCNInterpreter
        
        interpreter = MCNInterpreter()
        
        while True:
            try:
                line = input("mcn> ").strip()

                if line == "exit":
                    break
                elif line == "help":
                    print("Available commands:")
                    print("  exit - Exit REPL")
                    print("  help - Show this help")
                    print("  vars - Show variables")
                    print("  Dynamic systems: db, http, ai, events, agents, storage")
                elif line == "vars":
                    if interpreter.variables:
                        for name, value in interpreter.variables.items():
                            print(f"  {name} = {repr(value)}")
                    else:
                        print("  No variables defined")
                elif line:
                    result = interpreter.execute(line, quiet=True)
                    if result is not None:
                        print(f"=> {result}")

            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except Exception as e:
                print(f"Error: {e}")
    
    except ImportError as e:
        print(f"Could not load MCN interpreter: {e}")
        print("Running in basic mode...")
        # Fallback to basic mode
        while True:
            try:
                line = input("mcn> ").strip()
                if line == "exit":
                    break
                elif line:
                    print(f"Basic mode - received: {line}")
            except KeyboardInterrupt:
                break

    return 0


def generate_postman_collection(output_dir="postman_exports"):
    """Generate Postman collection"""
    try:
        sys.path.insert(0, os.path.join(script_dir, "mcn", "core_engine"))
        from mcn_postman_generator import generate_postman_collection as gen_collection
        
        print(f"Generating Postman collection to: {output_dir}")
        result = gen_collection(output_dir)
        
        print(f"✅ Generated {result['endpoints_count']} endpoints")
        print(f"📁 Collection: {result['collection_file']}")
        print(f"🌍 Environment: {result['environment_file']}")
        print(f"📖 README: {result['readme_file']}")
        print("\n🚀 Import these files into Postman to start testing!")
        
        return 0
    except Exception as e:
        print(f"❌ Failed to generate Postman collection: {e}")
        return 1


def generate_api_docs(output_dir="api_docs"):
    """Generate OpenAPI documentation"""
    try:
        sys.path.insert(0, os.path.join(script_dir, "mcn", "core_engine"))
        from mcn_swagger_generator import generate_swagger_docs
        
        print(f"Generating API documentation to: {output_dir}")
        result = generate_swagger_docs(output_dir)
        
        print(f"✅ Generated documentation for {result['endpoints_count']} endpoints")
        print(f"📄 OpenAPI Spec: {result['spec_file']}")
        print(f"🌐 Interactive Docs: {result['html_file']}")
        print("\n🚀 Open the HTML file in your browser for interactive documentation!")
        
        return 0
    except Exception as e:
        print(f"❌ Failed to generate API documentation: {e}")
        return 1


def generate_client_sdks(output_dir="generated_clients"):
    """Generate client SDKs"""
    try:
        sys.path.insert(0, os.path.join(script_dir, "mcn", "core_engine"))
        from mcn_codegen import generate_all_clients
        
        print(f"Generating client SDKs to: {output_dir}")
        result = generate_all_clients(output_dir)
        
        print(f"✅ Generated client SDKs successfully")
        print(f"🐍 Python SDK: {result['results']['python']['client_file']}")
        print(f"🟨 JavaScript SDK: {result['results']['javascript']['client_file']}")
        print(f"🐳 Docker Setup: {result['results']['docker']['compose_file']}")
        print("\n🚀 Use these SDKs to integrate MCN into your applications!")
        
        return 0
    except Exception as e:
        print(f"❌ Failed to generate client SDKs: {e}")
        return 1


def show_monitoring_dashboard():
    """Show monitoring dashboard"""
    try:
        sys.path.insert(0, os.path.join(script_dir, "mcn", "core_engine"))
        from mcn_monitoring import get_monitor, MCNAnalytics
        
        monitor = get_monitor()
        analytics = MCNAnalytics(monitor)
        
        print("📊 MCN Performance Dashboard")
        print("=" * 40)
        
        dashboard_data = analytics.generate_dashboard_data()
        
        # System Health
        health = dashboard_data['system_health']
        status_emoji = "🟢" if health['status'] == 'healthy' else "🟡" if health['status'] == 'warning' else "🔴"
        print(f"\n{status_emoji} System Health: {health['status'].upper()} (Score: {health['score']})")
        print(f"   Avg Response Time: {health.get('avg_response_time', 0):.3f}s")
        print(f"   Error Rate: {health.get('error_rate', 0):.1f}%")
        
        # Performance Report
        perf_report = dashboard_data['performance_report']
        if perf_report:
            print("\n📈 Performance Summary (Last 5 minutes):")
            for event_type, stats in perf_report.items():
                print(f"   {event_type}: {stats['count']} calls, avg {stats['avg_duration']:.3f}s")
        
        # Recent Anomalies
        anomalies = dashboard_data['anomalies']
        if anomalies:
            print("\n⚠️  Performance Anomalies Detected:")
            for anomaly in anomalies[:3]:  # Show top 3
                print(f"   {anomaly['event_type']}: {anomaly['severity']:.1f}x slower than baseline")
        else:
            print("\n✅ No performance anomalies detected")
        
        print("\n📊 For detailed metrics, check mcn_monitoring.db")
        
        return 0
    except Exception as e:
        print(f"❌ Failed to show monitoring dashboard: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
