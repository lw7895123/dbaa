"""
高并发订单监控系统安装配置
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="order-monitor-system",
    version="1.0.0",
    author="Order Monitor Team",
    author_email="team@ordermonitor.com",
    description="高并发订单监控系统",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/order-monitor-system",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.7.9",
    ],
    python_requires="==3.7.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "order-monitor=main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)