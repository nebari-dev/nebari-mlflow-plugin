# MLflow KServe Webhook Listener

Automatically deploy MLflow models to KServe when tagged for deployment.

## Overview

This service listens for MLflow model version tag events and automatically creates/deletes KServe InferenceServices based on the `deploy` tag. When a model version is tagged with `deploy=true`, the service deploys it to KServe. When the tag is removed, the service deletes the deployment.

## Features

- **Event-driven deployments**: Webhook-based real-time model deployments
- **Polling fallback**: Automatic fallback to polling mode if webhooks are unavailable
- **Automatic cleanup**: Removes InferenceServices when deploy tag is removed
- **Cloud-agnostic**: Works with GCS, S3, Azure Blob Storage, and more
- **Customizable**: Configurable resource limits, namespaces, and deployment parameters
- **KServe v2 protocol**: Uses the v2 inference protocol for broad model framework support

## Quick Start

See [k8s/README.md](k8s/README.md) for Kubernetes deployment instructions.

## How It Works

1. MLflow triggers a webhook when a model version is tagged with `deploy=true`
2. The webhook listener receives the event and fetches model details from MLflow
3. An InferenceService is created in the configured Kubernetes namespace
4. KServe deploys the model with the MLflow serving runtime (using v2 protocol)
5. When the `deploy` tag is removed, the InferenceService is deleted

## Configuration

All configuration is done via environment variables. See [k8s/README.md](k8s/README.md) for details.

## Development

```bash
# Install dependencies with pixi
pixi install

# Run tests
pixi run pytest

# Run the service locally
pixi run webhook-listener
```

## License

Apache-2.0
