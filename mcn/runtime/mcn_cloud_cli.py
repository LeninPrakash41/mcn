#!/usr/bin/env python3
"""
MCN Cloud CLI - Phase 3 Runtime Framework
Deploy and manage MCN applications in the cloud
"""

import argparse
import json
import requests
import os
import subprocess
import yaml
from typing import Dict, Any


class MCNCloudCLI:
    def __init__(self):
        self.api_base = os.getenv("MCN_CLOUD_API", "https://api.mcn-cloud.com")
        self.auth_token = os.getenv("MCN_CLOUD_TOKEN")

    def deploy(self, script_path: str, env: str = "production", instances: int = 1):
        """Deploy MCN script to cloud"""
        if not os.path.exists(script_path):
            print(f"Error: Script {script_path} not found")
            return 1

        print(f"Deploying {script_path} to {env} environment...")

        # Read script content
        with open(script_path, "r") as f:
            script_content = f.read()

        # Create deployment payload
        deployment = {
            "name": os.path.basename(script_path).replace(".mcn", ""),
            "script": script_content,
            "environment": env,
            "instances": instances,
            "runtime": "mcn-2.0",
        }

        # Deploy via API
        response = self._api_call("POST", "/deployments", deployment)

        if response.get("success"):
            deployment_id = response["deployment_id"]
            endpoint_url = response["endpoint_url"]
            print(f"✓ Deployment successful!")
            print(f"  Deployment ID: {deployment_id}")
            print(f"  Endpoint URL: {endpoint_url}")
            print(f"  Instances: {instances}")
            return 0
        else:
            print(f"✗ Deployment failed: {response.get('error', 'Unknown error')}")
            return 1

    def scale(self, app_name: str, instances: int):
        """Scale MCN application"""
        print(f"Scaling {app_name} to {instances} instances...")

        response = self._api_call(
            "PUT", f"/deployments/{app_name}/scale", {"instances": instances}
        )

        if response.get("success"):
            print(f"✓ Scaled {app_name} to {instances} instances")
            return 0
        else:
            print(f"✗ Scaling failed: {response.get('error')}")
            return 1

    def logs(self, app_name: str, tail: bool = False, lines: int = 100):
        """Get application logs"""
        print(f"Fetching logs for {app_name}...")

        params = {"lines": lines}
        if tail:
            params["tail"] = "true"

        response = self._api_call("GET", f"/deployments/{app_name}/logs", params=params)

        if response.get("success"):
            logs = response.get("logs", [])
            for log_entry in logs:
                timestamp = log_entry.get("timestamp", "")
                level = log_entry.get("level", "INFO")
                message = log_entry.get("message", "")
                print(f"[{timestamp}] {level}: {message}")
            return 0
        else:
            print(f"✗ Failed to fetch logs: {response.get('error')}")
            return 1

    def status(self, app_name: str = None):
        """Get deployment status"""
        if app_name:
            print(f"Status for {app_name}:")
            response = self._api_call("GET", f"/deployments/{app_name}")
        else:
            print("All deployments:")
            response = self._api_call("GET", "/deployments")

        if response.get("success"):
            if app_name:
                deployment = response["deployment"]
                self._print_deployment_status(deployment)
            else:
                deployments = response.get("deployments", [])
                for deployment in deployments:
                    self._print_deployment_status(deployment)
            return 0
        else:
            print(f"✗ Failed to get status: {response.get('error')}")
            return 1

    def rollback(self, app_name: str, version: str):
        """Rollback to previous version"""
        print(f"Rolling back {app_name} to version {version}...")

        response = self._api_call(
            "POST", f"/deployments/{app_name}/rollback", {"version": version}
        )

        if response.get("success"):
            print(f"✓ Rolled back {app_name} to version {version}")
            return 0
        else:
            print(f"✗ Rollback failed: {response.get('error')}")
            return 1

    def delete(self, app_name: str):
        """Delete deployment"""
        print(f"Deleting deployment {app_name}...")

        response = self._api_call("DELETE", f"/deployments/{app_name}")

        if response.get("success"):
            print(f"✓ Deleted deployment {app_name}")
            return 0
        else:
            print(f"✗ Delete failed: {response.get('error')}")
            return 1

    def _api_call(
        self, method: str, endpoint: str, data: Dict = None, params: Dict = None
    ) -> Dict[str, Any]:
        """Make API call to MCN Cloud"""
        url = f"{self.api_base}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}" if self.auth_token else "",
        }

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}

            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def _print_deployment_status(self, deployment: Dict):
        """Print deployment status in formatted way"""
        name = deployment.get("name", "Unknown")
        status = deployment.get("status", "Unknown")
        instances = deployment.get("instances", 0)
        endpoint = deployment.get("endpoint_url", "N/A")
        version = deployment.get("version", "N/A")

        print(f"  Name: {name}")
        print(f"  Status: {status}")
        print(f"  Instances: {instances}")
        print(f"  Endpoint: {endpoint}")
        print(f"  Version: {version}")
        print("-" * 40)


def main():
    parser = argparse.ArgumentParser(description="MCN Cloud CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy MCN script")
    deploy_parser.add_argument("script", help="MCN script file to deploy")
    deploy_parser.add_argument(
        "--env", default="production", help="Environment (default: production)"
    )
    deploy_parser.add_argument(
        "--instances", type=int, default=1, help="Number of instances (default: 1)"
    )

    # Scale command
    scale_parser = subparsers.add_parser("scale", help="Scale application")
    scale_parser.add_argument("app", help="Application name")
    scale_parser.add_argument("instances", type=int, help="Number of instances")

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Get application logs")
    logs_parser.add_argument("app", help="Application name")
    logs_parser.add_argument("--tail", action="store_true", help="Follow logs")
    logs_parser.add_argument(
        "--lines", type=int, default=100, help="Number of lines (default: 100)"
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Get deployment status")
    status_parser.add_argument("app", nargs="?", help="Application name (optional)")

    # Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback deployment")
    rollback_parser.add_argument("app", help="Application name")
    rollback_parser.add_argument("version", help="Version to rollback to")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete deployment")
    delete_parser.add_argument("app", help="Application name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    cli = MCNCloudCLI()

    if args.command == "deploy":
        return cli.deploy(args.script, args.env, args.instances)
    elif args.command == "scale":
        return cli.scale(args.app, args.instances)
    elif args.command == "logs":
        return cli.logs(args.app, args.tail, args.lines)
    elif args.command == "status":
        return cli.status(args.app)
    elif args.command == "rollback":
        return cli.rollback(args.app, args.version)
    elif args.command == "delete":
        return cli.delete(args.app)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    exit(main())
