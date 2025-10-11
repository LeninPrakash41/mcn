"""
Enhanced MCN CLI with Package Management
Provides command-line interface for package operations, model management, and registry
"""

import argparse
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

from .mcn_module_system import MCNModuleSystem
from .mcn_ai_models import MCNAIModelManager
from .mcn_registry import MCNPackageRegistry
from .mcn_interpreter import MCNInterpreter


class MCNEnhancedCLI:
    """Enhanced CLI for MCN with package management"""
    
    def __init__(self):
        self.module_system = MCNModuleSystem()
        self.ai_manager = MCNAIModelManager()
        self.registry = MCNPackageRegistry()
        self.interpreter = MCNInterpreter()
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser"""
        parser = argparse.ArgumentParser(
            description="MCN Enhanced CLI - AI-First Programming Language",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  mcn run script.mcn                    # Run MCN script
  mcn install ai_v3                     # Install package
  mcn search "machine learning"         # Search packages
  mcn register my-model openai gpt-4    # Register AI model
  mcn models list                       # List AI models
  mcn create-package my-pkg             # Create package template
  mcn publish my-package.zip            # Publish package
            """
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # Run command
        run_parser = subparsers.add_parser('run', help='Run MCN script')
        run_parser.add_argument('file', help='MCN script file to run')
        run_parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode')
        
        # Package management commands
        pkg_parser = subparsers.add_parser('install', help='Install package')
        pkg_parser.add_argument('package', help='Package name to install')
        pkg_parser.add_argument('--version', '-v', default='latest', help='Package version')
        
        search_parser = subparsers.add_parser('search', help='Search packages')
        search_parser.add_argument('query', nargs='?', default='', help='Search query')
        search_parser.add_argument('--category', '-c', help='Filter by category')
        search_parser.add_argument('--limit', '-l', type=int, default=10, help='Result limit')
        
        list_parser = subparsers.add_parser('list', help='List installed packages')
        list_parser.add_argument('--all', '-a', action='store_true', help='Include available packages')
        
        uninstall_parser = subparsers.add_parser('uninstall', help='Uninstall package')
        uninstall_parser.add_argument('package', help='Package name to uninstall')
        
        # AI model management commands
        models_parser = subparsers.add_parser('models', help='AI model management')
        models_subparsers = models_parser.add_subparsers(dest='models_command')
        
        models_list_parser = models_subparsers.add_parser('list', help='List AI models')
        models_list_parser.add_argument('--provider', '-p', help='Filter by provider')
        
        models_register_parser = models_subparsers.add_parser('register', help='Register AI model')
        models_register_parser.add_argument('name', help='Model name')
        models_register_parser.add_argument('provider', help='Provider (openai, anthropic, etc.)')
        models_register_parser.add_argument('model_id', nargs='?', help='Provider model ID')
        models_register_parser.add_argument('--config', help='JSON config string')
        
        models_set_parser = models_subparsers.add_parser('set', help='Set active model')
        models_set_parser.add_argument('name', help='Model name')
        
        models_delete_parser = models_subparsers.add_parser('delete', help='Delete model')
        models_delete_parser.add_argument('name', help='Model name')
        
        models_run_parser = models_subparsers.add_parser('run', help='Run AI model')
        models_run_parser.add_argument('prompt', help='Prompt text')
        models_run_parser.add_argument('--model', '-m', help='Model name')
        models_run_parser.add_argument('--max-tokens', type=int, default=150, help='Max tokens')
        
        # Package development commands\n        create_parser = subparsers.add_parser('create-package', help='Create package template')
        create_parser.add_argument('name', help='Package name')
        create_parser.add_argument('description', nargs='?', default='', help='Package description')
        create_parser.add_argument('--author', '-a', default='Anonymous', help='Author name')
        
        publish_parser = subparsers.add_parser('publish', help='Publish package')
        publish_parser.add_argument('package', help='Package file (.zip)')
        publish_parser.add_argument('--api-key', help='Registry API key')
        
        # Registry commands
        registry_parser = subparsers.add_parser('registry', help='Registry operations')
        registry_subparsers = registry_parser.add_subparsers(dest='registry_command')
        
        registry_stats_parser = registry_subparsers.add_parser('stats', help='Registry statistics')
        registry_popular_parser = registry_subparsers.add_parser('popular', help='Popular packages')
        registry_recent_parser = registry_subparsers.add_parser('recent', help='Recent packages')
        
        # Info commands
        info_parser = subparsers.add_parser('info', help='Package information')
        info_parser.add_argument('package', help='Package name')
        
        version_parser = subparsers.add_parser('version', help='Show MCN version')
        
        return parser
    
    def run_command(self, args: argparse.Namespace) -> int:
        """Execute the specified command"""
        try:
            if args.command == 'run':
                return self._run_script(args)
            elif args.command == 'install':
                return self._install_package(args)
            elif args.command == 'search':
                return self._search_packages(args)
            elif args.command == 'list':
                return self._list_packages(args)
            elif args.command == 'uninstall':
                return self._uninstall_package(args)
            elif args.command == 'models':
                return self._handle_models_command(args)
            elif args.command == 'create-package':
                return self._create_package(args)
            elif args.command == 'publish':
                return self._publish_package(args)
            elif args.command == 'registry':
                return self._handle_registry_command(args)
            elif args.command == 'info':
                return self._show_package_info(args)
            elif args.command == 'version':
                return self._show_version()
            else:
                print("Unknown command. Use --help for usage information.")
                return 1
                
        except Exception as e:
            print(f"Error: {e}")
            return 1
    
    def _run_script(self, args: argparse.Namespace) -> int:
        """Run MCN script"""
        script_path = Path(args.file)
        
        if not script_path.exists():
            print(f"Error: Script file '{args.file}' not found")
            return 1
        
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            result = self.interpreter.execute(code, str(script_path), quiet=args.quiet)
            
            if not args.quiet:
                print(f"\nScript executed successfully")
            
            return 0
            
        except Exception as e:
            print(f"Execution failed: {e}")
            return 1
    
    def _install_package(self, args: argparse.Namespace) -> int:
        """Install package"""
        result = self.module_system.install_package(args.package, args.version)
        print(result)
        return 0 if "successfully" in result else 1
    
    def _search_packages(self, args: argparse.Namespace) -> int:
        """Search packages"""
        packages = self.registry.search_packages(args.query, args.category or "", args.limit)
        
        if not packages:
            print("No packages found matching your criteria")
            return 0
        
        print(f"Found {len(packages)} package(s):")
        print()
        
        for pkg in packages:
            print(f"📦 {pkg['name']} v{pkg['version']}")
            print(f"   {pkg['description']}")
            print(f"   Author: {pkg['author']} | Downloads: {pkg['downloads']}")
            if pkg.get('keywords'):
                print(f"   Keywords: {', '.join(pkg['keywords'])}")
            print()
        
        return 0
    
    def _list_packages(self, args: argparse.Namespace) -> int:
        """List packages"""
        if args.all:
            packages = self.registry.search_packages(limit=100)
            print("Available packages:")
        else:
            packages = self.module_system.list_packages(installed_only=True)
            print("Installed packages:")
        
        if not packages:
            print("No packages found")
            return 0
        
        for pkg in packages:
            status = "✓" if pkg.get('installed', False) else " "
            print(f"{status} {pkg['name']} v{pkg['version']} - {pkg['description']}")
        
        return 0
    
    def _uninstall_package(self, args: argparse.Namespace) -> int:
        """Uninstall package"""
        result = self.module_system.uninstall_package(args.package)
        print(result)
        return 0 if "successfully" in result else 1
    
    def _handle_models_command(self, args: argparse.Namespace) -> int:
        """Handle AI models commands"""
        if args.models_command == 'list':
            return self._list_models(args)
        elif args.models_command == 'register':
            return self._register_model(args)
        elif args.models_command == 'set':
            return self._set_model(args)
        elif args.models_command == 'delete':
            return self._delete_model(args)
        elif args.models_command == 'run':
            return self._run_model(args)
        else:
            print("Unknown models command. Use 'mcn models --help' for usage.")
            return 1
    
    def _list_models(self, args: argparse.Namespace) -> int:
        """List AI models"""
        models = self.ai_manager.list_models(args.provider)
        
        if not models:
            print("No models found")
            return 0
        
        print("Available AI models:")
        print()
        
        for model in models:
            active_marker = "🟢" if model['active'] else "  "
            fine_tuned_marker = "🔧" if model['fine_tuned'] else "  "
            
            print(f"{active_marker}{fine_tuned_marker} {model['name']}")
            print(f"     Provider: {model['provider']}")
            print(f"     Model ID: {model['model_id']}")
            print(f"     Usage: {model['usage_count']} times")
            print()
        
        return 0
    
    def _register_model(self, args: argparse.Namespace) -> int:
        """Register AI model"""
        config = {}
        if args.config:
            try:
                config = json.loads(args.config)
            except json.JSONDecodeError:
                print("Error: Invalid JSON config")
                return 1
        
        result = self.ai_manager.register_model(
            args.name, args.provider, args.model_id, **config
        )
        print(result)
        return 0
    
    def _set_model(self, args: argparse.Namespace) -> int:
        """Set active model"""
        result = self.ai_manager.set_active_model(args.name)
        print(result)
        return 0 if "set to" in result else 1
    
    def _delete_model(self, args: argparse.Namespace) -> int:
        """Delete model"""
        result = self.ai_manager.delete_model(args.name)
        print(result)
        return 0 if "successfully" in result else 1
    
    def _run_model(self, args: argparse.Namespace) -> int:
        """Run AI model"""
        result = self.ai_manager.run_model(
            args.prompt, args.model, max_tokens=args.max_tokens
        )
        
        if "error" in result:
            print(f"Error: {result['error']}")
            return 1
        
        print(f"Model: {result.get('model', 'unknown')}")
        print(f"Response: {result.get('response', 'No response')}")
        
        if result.get('simulated'):
            print("(Simulated response - configure API keys for real responses)")
        
        return 0
    
    def _create_package(self, args: argparse.Namespace) -> int:
        """Create package template"""
        result = self.registry.create_package_template(
            args.name, args.description, args.author
        )
        print(result)
        return 0 if "created" in result else 1
    
    def _publish_package(self, args: argparse.Namespace) -> int:
        """Publish package"""
        result = self.registry.publish_package(args.package, args.api_key)
        print(result)
        return 0 if "successfully" in result else 1
    
    def _handle_registry_command(self, args: argparse.Namespace) -> int:
        """Handle registry commands"""
        if args.registry_command == 'stats':
            return self._show_registry_stats()
        elif args.registry_command == 'popular':
            return self._show_popular_packages()
        elif args.registry_command == 'recent':
            return self._show_recent_packages()
        else:
            print("Unknown registry command")
            return 1
    
    def _show_registry_stats(self) -> int:
        """Show registry statistics"""
        stats = self.registry.get_registry_stats()
        
        print("MCN Package Registry Statistics:")
        print(f"📦 Total packages: {stats['total_packages']}")
        print(f"⬇️  Total downloads: {stats['total_downloads']}")
        print(f"🏷️  Categories: {stats['categories']}")
        print(f"🌐 Registry URL: {stats['registry_url']}")
        
        return 0
    
    def _show_popular_packages(self) -> int:
        """Show popular packages"""
        packages = self.registry.get_popular_packages()
        
        print("Most Popular Packages:")
        print()
        
        for i, pkg in enumerate(packages, 1):
            print(f"{i:2d}. {pkg['name']} v{pkg['version']}")
            print(f"     {pkg['description']}")
            print(f"     Downloads: {pkg['downloads']}")
            print()
        
        return 0
    
    def _show_recent_packages(self) -> int:
        """Show recent packages"""
        packages = self.registry.get_recent_packages()
        
        print("Recently Updated Packages:")
        print()
        
        for pkg in packages:
            print(f"📦 {pkg['name']} v{pkg['version']}")
            print(f"   {pkg['description']}")
            print(f"   Author: {pkg['author']}")
            print()
        
        return 0
    
    def _show_package_info(self, args: argparse.Namespace) -> int:
        """Show package information"""
        info = self.registry.get_package_info(args.package)
        
        if not info:
            print(f"Package '{args.package}' not found")
            return 1
        
        print(f"📦 {info['name']} v{info['version']}")
        print(f"Description: {info['description']}")
        print(f"Author: {info.get('author', 'Unknown')}")
        print(f"License: {info.get('license', 'Unknown')}")
        
        if info.get('dependencies'):
            print(f"Dependencies: {', '.join(info['dependencies'])}")
        
        if info.get('functions'):
            print(f"Functions: {', '.join(info['functions'])}")
        
        if info.get('keywords'):
            print(f"Keywords: {', '.join(info['keywords'])}")
        
        print(f"Downloads: {info.get('downloads', 0)}")
        
        return 0
    
    def _show_version(self) -> int:
        """Show MCN version"""
        print("MCN (Modern Computing Notation) v3.0.0")
        print("The Industry Standard for AI-Powered Business Automation")
        print()
        print("Features:")
        print("✓ Enhanced package management")
        print("✓ Multi-provider AI model support")
        print("✓ IoT and edge computing integration")
        print("✓ Event-driven programming")
        print("✓ Autonomous AI agents")
        print("✓ Natural language programming")
        print("✓ AI-powered data pipelines")
        print()
        print("Visit https://mslang.org for documentation and examples")
        
        return 0


def main():
    """Main CLI entry point"""
    cli = MCNEnhancedCLI()
    parser = cli.create_parser()
    
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    
    args = parser.parse_args()
    return cli.run_command(args)


if __name__ == "__main__":
    sys.exit(main())