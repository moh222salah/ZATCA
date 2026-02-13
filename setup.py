"""
Setup configuration for ZATCA Compliance Monitor
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="zatca-compliance-monitor",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Production-grade ZATCA e-invoicing compliance validator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/zatca-compliance-monitor",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Office/Business :: Financial :: Accounting",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "pydantic>=2.0.0",
        "xmltodict>=0.13.0",
        "python-dateutil>=2.8.2",
        "cryptography>=41.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "zatca-monitor=zatca_monitor.main:main",
        ],
    },
)
