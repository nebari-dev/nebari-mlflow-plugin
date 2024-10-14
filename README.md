# Nebari MLflow Plugin

**Table of Contents**

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [License](#license)

## Introduction
This MLflow extension currently only supports Azure Nebari deployments, but aims to integrate into Nebari deployments utilizing the Azure, AWS, GCP, and DO providers. It provides a robust, collaborative environment for AI/ML professionals to manage experiments, track metrics, and deploy models.

### Features
**Centralized Artifact Repository**: Store and manage all your metrics, parameters, and artifacts in a single location, accessible across the multi-tenant platform.

**Experiment Tracking**: Log, query, and visualize metrics to understand and compare different runs and models.

**Automated Configuration**: Simply type import mlflow in your Python script, and you're already configured to communicate with the remote multi-tenant MLflow server—no additional setup required.

### Installation
Prerequisites:
- Nebari must be deployed using the Azure provider at the moment
- Nebari version 2024.6.1 or later

Installing the MLflow extension is as straightforward as installing a Python package. Run the following commands:

```bash
git clone nebari-mlflow-plugin
cd nebari-mlflow-plugin
pip install nebari-mlflow-plugin
```
This command installs the Python package and also creates the necessary infrastructure to run MLflow on the AI Platform.

### Configuration
After installation, the MLflow extension is automatically configured to work with the AI Platform. To access the MLflow interface, navigate to <https://[your-nebari-domain]/mlflow>.

For Azure, your app registration will need RBAC permissions in addition to the typical Contributor permissons.  We recommend you create a custom role scoped at the resource_group (usually named \<project_name\>-\<namespace\> where the values are what you set in nebari-config.yaml), and add the Microsoft.Authorization/roleAssignments/read, Microsoft.Authorization/roleAssignments/write, Microsoft.Authorization/roleAssignments/delete permissions.  Then create a role assignment of that role to the nebari app registration service principal.

#### Configuring MLflow Tracking URL
You may set the `MLFLOW_TRACKING_URL` to configure mlflow in individual users' Nebari instances by adding or updating an additional block in your Nebari configuration file. Be sure to replace `{project_name}` and `{namespace}` with the values from your own nebari config file e.g. `http://mynebari-mlflow-tracking.dev.svc:5000`.

```yaml
jupyterhub:
  overrides:
    singleuser:
      extraEnv:
        MLFLOW_TRACKING_URI: "http://{project_name}-mlflow-tracking.{namespace}.svc:5000" 
```

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

`nebari-mlflow-plugin` is distributed under the terms of the [Apache](./LICENSE.md) license.
