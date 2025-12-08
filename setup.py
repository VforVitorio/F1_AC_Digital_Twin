from setuptools import setup, find_packages

setup(
    name="f1-digital-twin",
    version="1.0.0",
    description="F1 Digital Twin - Análisis de telemetría con ecuaciones de ingeniería",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "matplotlib>=3.7.0",
        "seaborn>=0.12.0",
        "scipy>=1.10.0",
        "pysindy>=1.7.0",
        "jupyter>=1.0.0",
        "notebook>=7.0.0",
        "python-dateutil>=2.8.2",
        "python-dotenv>=1.0.0",
        "confluent-kafka>=2.3.0",
        "influxdb-client>=1.38.0",
    ],
    python_requires=">=3.8",
)
