# Nebari Plugin MLflow AWS

[![PyPI - Version](https://img.shields.io/pypi/v/nebari-plugin-mlflow-chart.svg)](https://pypi.org/project/nebari-plugin-mlflow-chart)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/nebari-plugin-mlflow-chart.svg)](https://pypi.org/project/nebari-plugin-mlflow-chart)

-----

**Table of Contents**

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [License](#license)

## Introduction
This MLflow extension is designed to integrate seamlessly into the AI Platform, providing a robust environment for AI/ML professionals to manage experiments, track metrics, and deploy models. This AI Platform serves as a collaborative experimentation space with a focus on AI robustness, testing and evaluation, and AI red teaming for adversarial attacks in AI.

### Features
**Centralized Artifact Repository**: Store and manage all your metrics, parameters, and artifacts in a single location, accessible across the multi-tenant platform.

**Experiment Tracking**: Log, query, and visualize metrics to understand and compare different runs and models.

**Automated Configuration**: Simply type import mlflow in your Python script, and you're already configured to communicate with the remote multi-tenant MLflow server—no additional setup required.

### Installation
Installing the MLflow extension is as straightforward as installing a Python package. Run the following commands:

```bash
git clone nebari-plugin-mlflow-aws
cd nebari-plugin-mlflow-aws/
pip install nebari-plugin-mlflow-aws
```
This command installs the Python package and also creates the necessary infrastructure to run MLflow on the AI Platform.

### Configuration
After installation, the MLflow extension is automatically configured to work with the AI Platform. To access the MLflow interface, navigate to <https://jatic-te-dev.metrostar.cloud/mlflow>.

### Usage
Getting started with the MLflow extension is incredibly simple. To track an experiment:

Navigate to the MLFLow extension URL and create a new experiment.
In your Python script, import MLflow and start logging metrics.
```python
import mlflow

# Start an experiment
with mlflow.start_run() as run:
    mlflow.log_metric("accuracy", 0.9)
    mlflow.log_artifact("path/to/your/artifact")
```
With the above code, your metrics and artifacts are automatically stored and accessible via the MLFlow extension URL.


## License

`nebari-plugin-mlflow-aws` is distributed under the terms of the [Apache](./LICENSE.md) license.
