#!/usr/bin/env python3
"""
MCN (Macincode Scripting Language) Setup
"""

from setuptools import setup, find_packages
import os


# Read README for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    return "MCN - Business automation scripting language with AI integration"


# Read requirements
def read_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "mcn", "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path, "r", encoding="utf-8") as f:
            return [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    return [
        "requests>=2.25.0",
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "python-dotenv>=0.19.0",
    ]


setup(
    name="mcn-lang",
    version="2.0.0",
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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Interpreters",
        "Topic :: Office/Business :: Financial",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
        "ai": ["openai>=0.27.0", "anthropic>=0.3.0"],
        "database": ["sqlalchemy>=1.4.0", "psycopg2-binary>=2.9.0", "pymongo>=3.12.0"],
        "cloud": [
            "boto3>=1.20.0",
            "azure-storage-blob>=12.0.0",
            "google-cloud-storage>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "mcn=mcn.core_engine.mcn_cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "mcn": [
            "examples/*.mcn",
            "use-cases/*.mcn",
            "mcn_packages/*.json",
            "docs/*.md",
            "studio/vscode-mcn/syntaxes/*.json",
            "studio/vscode-mcn/package.json",
            "web-playground/*.html",
            "web-playground/*.js",
            "web-playground/*.css",
        ],
    },
    zip_safe=False,
    keywords="mcn scripting automation ai business workflow",
    project_urls={
        "Bug Reports": "https://github.com/zeroappz/mcn/issues",
        "Source": "https://github.com/zeroappz/mcn",
        "Documentation": "https://docs.mslang.org",
    },
)
