from setuptools import setup

setup(
    name="demo_python",
    version="0.1.0",
    entry_points={"console_scripts": ["demo_node = demo_python.node:main"]},
)
