#!/usr/bin/env python3
import logging
import os
import sys
import time

import mlflow
from mlflow import MlflowClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Wait for MLflow server to be ready
max_retries = 30
retry_delay = 2

# Get cycle time from environment variable (default to 10 seconds)
cycle_time = int(os.getenv("DEPLOYMENT_STATUS_CYCLE_TIME", "10"))

mlflow.set_tracking_uri(uri="http://mlflow:5000")
client = MlflowClient()

logger.info("Waiting for MLflow server to be ready...")
for i in range(max_retries):
    try:
        client.search_registered_models()
        logger.info("MLflow server is ready!")
        break
    except Exception:
        if i == max_retries - 1:
            logger.error(f"Failed to connect to MLflow server after {max_retries} attempts")
            sys.exit(1)
        logger.info(f"Attempt {i+1}/{max_retries}: MLflow server not ready yet, waiting {retry_delay}s...")
        time.sleep(retry_delay)

# Note: Webhook registration is now handled by the webhook-listener service on startup
logger.info("Webhook registration is handled by the webhook-listener service")

# Check if any models are registered
model_exists = False
try:
    registered_models = client.search_registered_models()
    if len(registered_models) > 0:
        logger.info(f"Found {len(registered_models)} registered model(s). Skipping model creation.")
        model_exists = True
    else:
        logger.info("No models registered. Creating initial model...")
except Exception as e:
    logger.error(f"Error checking registered models: {e}")
    logger.info("Proceeding with model creation...")

if not model_exists:
    # Create the initial model
    import pandas as pd
    from mlflow.models import infer_signature
    from sklearn import datasets
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split

    # Load the Iris dataset
    X, y = datasets.load_iris(return_X_y=True)

    # Split the data into training and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Define the model hyperparameters
    params = {
        "solver": "lbfgs",
        "max_iter": 1000,
        "random_state": 8888,
    }

    # Train the model
    lr = LogisticRegression(**params)
    lr.fit(X_train, y_train)

    # Predict on the test set
    y_pred = lr.predict(X_test)

    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)

    # Create a new MLflow Experiment
    mlflow.set_experiment("MLflow Quickstart")

    # Start an MLflow run
    with mlflow.start_run():
        # Log the hyperparameters
        mlflow.log_params(params)

        # Log the loss metric
        mlflow.log_metric("accuracy", accuracy)

        # Infer the model signature
        signature = infer_signature(X_train, lr.predict(X_train))

        # Log the model, which inherits the parameters and metric
        model_info = mlflow.sklearn.log_model(
            sk_model=lr,
            name="iris_model",
            signature=signature,
            input_example=X_train,
            registered_model_name="tracking-quickstart",
        )

        # Set a tag that we can use to remind ourselves what this model was for
        mlflow.set_logged_model_tags(
            model_info.model_id, {"Training Info": "Basic LR model for iris data"}
        )

    logger.info("Model created successfully!")

# Get the registered model name and latest version
model_name = "tracking-quickstart"

# Get the latest model version
latest_versions = client.get_latest_versions(model_name)
if not latest_versions:
    logger.error("No model versions found. Exiting.")
    sys.exit(1)

model_version = latest_versions[0].version

# Cycle through deploy tag values: true, false
deploy_values = ["true", "false"]
status_index = 0

logger.info(f"Starting deploy tag cycling for model: {model_name} version: {model_version}")
logger.info("This will trigger InferenceService creation/deletion in the webhook-listener")
logger.info("Press Ctrl+C to stop...")

try:
    while True:
        current_value = deploy_values[status_index]

        # Set the deploy tag on the model version
        try:
            logger.info(f"Setting deploy tag to: {current_value}")
            client.set_model_version_tag(model_name, model_version, "deploy", current_value)
        except Exception as e:
            logger.error(f"Error setting tag: {e}")

        # Move to next value
        status_index = (status_index + 1) % len(deploy_values)

        # Wait before next update
        time.sleep(cycle_time)

except KeyboardInterrupt:
    logger.info("Stopping deployment status cycling...")
    sys.exit(0)
