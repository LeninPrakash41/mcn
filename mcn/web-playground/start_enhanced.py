#!/usr/bin/env python3
"""
Enhanced MCN Web Playground Startup Script
Starts the web playground with all v3.0 features enabled
"""

import os
import sys
import subprocess
import webbrowser
import time
import threading
from pathlib import Path

def check_dependencies():
    """Check and install required dependencies"""
    required_packages = [
        'flask',
        'flask-cors', 
        'flask-socketio',
        'python-socketio',
        'eventlet'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"📦 Installing missing packages: {', '.join(missing_packages)}")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install'
        ] + missing_packages)
        print("✅ Dependencies installed successfully!")
    else:
        print("✅ All dependencies are already installed")

def setup_environment():
    """Setup MCN environment for web playground"""
    print("🔧 Setting up MCN environment...")
    
    # Add MCN paths to Python path
    mcn_root = Path(__file__).parent.parent
    core_engine_path = mcn_root / 'core_engine'
    
    if str(core_engine_path) not in sys.path:
        sys.path.insert(0, str(core_engine_path))
    
    if str(mcn_root) not in sys.path:
        sys.path.insert(0, str(mcn_root))
    
    # Set environment variables
    os.environ['MCN_WEB_PLAYGROUND'] = '1'
    os.environ['MCN_V3_FEATURES'] = '1'
    os.environ['FLASK_ENV'] = 'development'
    
    print("✅ Environment setup complete!")

def start_playground_server():
    """Start the enhanced web playground server"""
    print("🚀 Starting MCN Web Playground Server...")
    
    try:
        # Change to web-playground directory
        os.chdir(Path(__file__).parent)
        
        # Import and run the server
        from server import app, socketio
        
        print("🌐 MCN Web Playground starting...")
        print("📱 Features enabled:")
        print("   ✅ Real-time WebSocket communication")
        print("   ✅ Session management")
        print("   ✅ MCN v3.0 AI integration")
        print("   ✅ IoT automation support")
        print("   ✅ Data pipeline processing")
        print("   ✅ Enhanced error handling")
        print("   ✅ Background task execution")
        
        # Start server in a separate thread
        def run_server():
            socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # Wait a moment for server to start
        time.sleep(2)
        
        # Open browser
        playground_url = "http://localhost:5000"
        print(f"🌍 Opening browser to: {playground_url}")
        webbrowser.open(playground_url)
        
        print("\n" + "="*60)
        print("🎉 MCN Web Playground is now running!")
        print("📖 Try these examples:")
        print("   • Hello World - Basic MCN syntax")
        print("   • AI Integration - GPT model usage")
        print("   • IoT Automation - Device control")
        print("   • Data Pipeline - Processing workflows")
        print("   • Async Tasks - Background execution")
        print("\n💡 Tips:")
        print("   • Use session management for persistent variables")
        print("   • Try real-time output with WebSocket connection")
        print("   • Explore v3.0 features like register(), device(), pipeline()")
        print("="*60)
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Shutting down MCN Web Playground...")
            
    except ImportError as e:
        print(f"❌ Failed to import server module: {e}")
        print("Make sure you're running from the web-playground directory")
        return False
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return False
    
    return True

def show_startup_info():
    """Show startup information and instructions"""
    print("🚀 MCN Web Playground - Enhanced Edition")
    print("=" * 50)
    print("🎯 Features:")
    print("  • Real-time code execution")
    print("  • WebSocket-based output streaming")
    print("  • Session persistence")
    print("  • MCN v3.0 AI integration")
    print("  • IoT device simulation")
    print("  • Data pipeline processing")
    print("  • Enhanced error handling")
    print("  • Background task management")
    print()

def main():
    """Main startup function"""
    show_startup_info()
    
    try:
        # Check dependencies
        check_dependencies()
        
        # Setup environment
        setup_environment()
        
        # Start server
        success = start_playground_server()
        
        if not success:
            print("❌ Failed to start MCN Web Playground")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n👋 Startup cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()