# Docker Compose Test Environment

This directory contains a Docker Compose setup for testing the MLflow KServe Webhook Listener locally.

## Services

1. **mlflow** - MLflow tracking server with SQLite backend and webhook support
2. **webhook-listener** - The MLflow KServe webhook listener service (the main package!)
3. **model-create** - A helper service that creates a test model and cycles the `deploy` tag

## Prerequisites

- Docker and Docker Compose installed
- [mkcert](https://github.com/FiloSottile/mkcert) for easy local SSL certificate generation

## Quick Start

### 1. Generate SSL certificates

```bash
make certs
```

This generates `localhost.pem` and `localhost-key.pem` for HTTPS support.

### 2. (Optional) Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` if you want to customize settings (cycle time, webhook secret, etc).

### 3. Start services

```bash
docker compose up --build
```

## What Happens

1. **MLflow starts** and creates a SQLite database in `./mlflow-data/`
2. **Webhook listener starts** and automatically:
   - Registers itself as a webhook with MLflow on startup
   - Listens for incoming webhook events on port 18347
   - Logs all webhook events and processing
3. **Model-create service**:
   - Waits for MLflow to be ready
   - Creates a test Iris classification model (if none exists)
   - Cycles the `deploy` tag between `true` and `false` every 10 seconds (configurable)
4. **Webhook events flow**:
   - When `deploy=true`, webhook-listener receives event and logs deployment trigger
   - When `deploy=false`, webhook-listener receives event and logs undeployment trigger
   - All webhook signatures are verified for security

## Accessing Services

- **MLflow UI**: http://localhost:5000
  - View models, runs, and experiments
  - Check registered webhooks under Settings
- **Webhook listener**:
  - Base URL: http://localhost:18347
  - Health check: http://localhost:18347/health
  - Services list: http://localhost:18347/services

## Viewing Logs

Watch logs from all services:
```bash
docker compose logs -f
```

Watch specific service logs:
```bash
docker compose logs -f webhook-listener
docker compose logs -f model-create
docker compose logs -f mlflow
```

## Testing the Webhook Flow

1. Start the services:
   ```bash
   docker compose up --build
   ```

2. Watch the webhook-listener logs:
   ```bash
   docker compose logs -f webhook-listener
   ```

3. You should see:
   - Webhook registration on startup
   - Periodic webhook events (every 10 seconds) when model-create cycles the deploy tag
   - Signature verification success messages
   - Event processing logs showing deploy/undeploy triggers

4. Optional: Manually trigger events via MLflow UI:
   - Go to http://localhost:5000
   - Navigate to the "tracking-quickstart" model
   - Go to the latest version
   - Add/change/remove the `deploy` tag
   - Watch the webhook-listener logs react in real-time

## Configuration

The webhook-listener service is configured via environment variables in [compose.yaml](./compose.yaml):

| Variable | Description | Default |
|----------|-------------|---------|
| `MLFLOW_KSERVE_MLFLOW_TRACKING_URI` | MLflow server URL | `http://mlflow:5000` |
| `MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET` | Shared secret for webhook signatures | From `.env` |
| `MLFLOW_KSERVE_MLFLOW_WEBHOOK_URL` | URL where this service receives webhooks | `https://webhook-listener:8000/webhook` |
| `MLFLOW_KSERVE_MLFLOW_WEBHOOK_NAME` | Name for the registered webhook | `mlflow-kserve-webhook` |
| `MLFLOW_KSERVE_STORAGE_URI_BASE` | Base path for model artifacts | `file:///mlflow/artifacts` |
| `MLFLOW_KSERVE_LOG_LEVEL` | Logging level | `DEBUG` |

## Cleanup

Remove SSL certificates:
```bash
make clean-certs
```

Remove MLflow data (database + artifacts):
```bash
make clean-data
```

Remove everything (certs + data):
```bash
make clean
```

Stop and remove containers:
```bash
docker compose down
```

Stop and remove containers + volumes:
```bash
docker compose down -v
```

## Notes

- This is a **test environment** - Kubernetes functionality is not tested here
- The webhook-listener now **automatically registers itself** with MLflow on startup
- The model-create service **no longer handles webhook registration** (that's done by webhook-listener)
- The model-create service will run indefinitely, cycling the `deploy` tag
- MLflow data persists in `./mlflow-data/` directory
- Press Ctrl+C to stop all services

## Differences from Old Setup

This setup replaces the old `docker-compose/listener/listener.py` with the full webhook-listener package:

**Old listener service**:
- Basic webhook signature verification
- No webhook registration (done by model-create)
- Stub processing logic

**New webhook-listener service** (your package!):
- Full webhook signature verification
- **Automatic webhook registration on startup** via lifespan event
- Complete event routing and processing
- MLflow client integration
- Pydantic configuration management
- Production-ready structure

The model-create service is now simplified - it only creates models and cycles tags, no longer managing webhook registration.
