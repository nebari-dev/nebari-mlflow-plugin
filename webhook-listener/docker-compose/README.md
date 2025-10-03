# Docker Setup

## Prerequisites

Install [mkcert](https://github.com/FiloSottile/mkcert) for easy local SSL certificate generation.

## Setup

1. Generate SSL certificates:
   ```bash
   make certs
   ```

2. Start services:
   ```bash
   docker-compose up
   ```

## Services

- **mlflow** - MLflow tracking server with webhook support
- **model-create** - Creates registered MLflow model and cycles through deployment status tags
- **webhook-listener** - HTTPS endpoint for receiving MLflow webhooks

## Cleanup

Remove SSL certificates:
```bash
make clean-certs
```

Remove MLflow data:
```bash
make clean-data
```

Remove everything (certs + data):
```bash
make clean
```

Stop and remove containers:
```bash
docker-compose down
```
