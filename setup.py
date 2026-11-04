#!/usr/bin/env python3
"""
MCN (Macincode Scripting Language) Setup
"""

from setuptools import setup, find_packages
import os
import re


# Read README for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    return "MCN - Business automation scripting language with AI integration"


# Runtime dependencies. Kept here (not read from a file) so every build — wheel,
# sdist or the one-line installer — gets the same list.
INSTALL_REQUIRES = [
    "requests>=2.28.0",
    "PyJWT>=2.8.0",
    "python-dotenv>=0.19.0",
    "anthropic>=0.84.0",       # ai(), Copilot, mcn generate
    "flask>=3.0.0",            # MCN Studio
    "flask-cors>=4.0.0",
    "fastapi>=0.104.0",        # mcn serve (with /docs)
    "uvicorn>=0.24.0",
]

# Optional features, installed with `mcn add <feature>` (see FEATURES in mcn_cli.py)
EXTRAS_REQUIRE = {
    "postgres": ["psycopg2-binary>=2.9.0"],
    "mongodb": ["pymongo>=4.0.0"],
    "ml": ["scikit-learn>=1.3.0", "pandas>=2.0.0", "numpy>=1.24.0"],
    "scheduler": ["apscheduler>=3.10.0"],
    "iot": ["pyserial>=3.5", "paho-mqtt>=2.0", "gpiozero>=2.0; platform_system == 'Linux'"],
    "dev": ["pytest>=7.0", "pytest-cov>=4.0"],
}


setup(
    name="mcn-lang",
    version=re.search(r'__version__ = "([^"]+)"', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcn", "version.py")).read()).group(1),
    author="MCN Foundation from Macincode",
    author_email="dev@mslang.org",
    description="Business automation scripting language with AI integration",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/mcn/mcn",
    packages=find_packages(include=["mcn", "mcn.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Interpreters",
        "Topic :: Office/Business :: Financial",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.10",
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    entry_points={
        "console_scripts": [
            "mcn=mcn.core_engine.mcn_cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "mcn": [
            "version.py",
            "fullstack/*.dart",
            "iot_firmware/*/*.ino",
            "studio/vscode-mcn/syntaxes/*.json",
            "studio/vscode-mcn/package.json",
            "studio/vscode-mcn/*.vsix",
            "web-playground/index.html",
            "web-playground/server.py",
            "web-playground/requirements.txt",
            "web-playground/static/css/*.css",
            "web-playground/static/js/*.js",
            "web-playground/static/preview/*.js",
            "web-playground/static/preview/*.css",
            "ui-kit/react/src/lib/*.ts",
            "ui-kit/react/src/components/ui/*.ts",
            "ui-kit/react/src/components/ui/*.tsx",
            "web-playground/scaffolds/*",
            "web-playground/scaffolds/.env.example",
            "web-playground/scaffolds/.github/workflows/*.yml",
            "web-playground/playground_server/*.py",
            "web-playground/playground_server/*.html",
            "web-playground/playground_server/templates/*.json",
            "web-playground/playground_server/templates/*/*",
            "web-playground/playground_server/templates/*/*/*",
        ],
    },
    exclude_package_data={"mcn": ["web-playground/workspace/*", "web-playground/node_modules/*"]},
    zip_safe=False,
    keywords="mcn scripting automation ai business workflow",
    project_urls={
        "Bug Reports": "https://github.com/LeninPrakash41/mcn/issues",
        "Source": "https://github.com/LeninPrakash41/mcn",
        "Documentation": "https://docs.mslang.org",
    },
)
