#!/usr/bin/env python3
import time
import sys
import os
import logging
import mlflow
from mlflow import MlflowClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
    except Exception as e:
        if i == max_retries - 1:
            logger.error(f"Failed to connect to MLflow server after {max_retries} attempts")
            sys.exit(1)
        logger.info(f"Attempt {i+1}/{max_retries}: MLflow server not ready yet, waiting {retry_delay}s...")
        time.sleep(retry_delay)

# Check if webhook already exists and create if it doesn't
webhook_secret = os.getenv("WEBHOOK_SECRET")
webhook_url = "https://webhook-listener:8000/webhook"
webhook_exists = False

try:
    # Try to list existing webhooks
    webhooks = client.list_webhooks()
    for webhook in webhooks:
        if webhook.url == webhook_url:
            logger.info(f"Webhook already exists with ID: {webhook.webhook_id}")
            webhook_exists = True
            break
except Exception as e:
    logger.error(f"Error listing webhooks: {e}")

if not webhook_exists and webhook_secret:
    try:
        logger.info(f"Creating webhook to {webhook_url}...")
        webhook = client.create_webhook(
            name="model-lifecycle-webhook",
            url=webhook_url,
            events=["model_version_tag.set", "registered_model.created", "model_version.created"],
            description="Webhook for tracking model lifecycle events",
            secret=webhook_secret
        )
        logger.info(f"Webhook created successfully with ID: {webhook.webhook_id}")

        # Test the webhook
        logger.info("Testing webhook connectivity...")
        test_result = client.test_webhook(webhook.webhook_id)
        logger.info(f"Webhook test result: success={test_result.success}, status={test_result.response_status}, body={test_result.response_body}, error={test_result.error_message}")
    except Exception as e:
        logger.error(f"Error creating webhook: {e}")
        logger.warning("Continuing without webhook...")
elif not webhook_secret:
    logger.warning("WEBHOOK_SECRET not set, skipping webhook creation")

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
    from sklearn import datasets
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score
    from mlflow.models import infer_signature

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

# Cycle through deployment statuses
statuses = ["deploying", "running", "not deployed"]
status_index = 0

logger.info(f"Starting deployment status cycling for model: {model_name} version: {model_version}")
logger.info("Press Ctrl+C to stop...")

try:
    while True:
        current_status = statuses[status_index]

        # Set the deployment_status tag on the model version
        try:
            logger.info(f"Setting deployment_status to: {current_status}")
            client.set_model_version_tag(model_name, model_version, "deployment_status", current_status)
        except Exception as e:
            logger.error(f"Error setting tag: {e}")

        # Move to next status
        status_index = (status_index + 1) % len(statuses)

        # Wait before next update
        time.sleep(cycle_time)

except KeyboardInterrupt:
    logger.info("Stopping deployment status cycling...")
    sys.exit(0)
