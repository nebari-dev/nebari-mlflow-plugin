# Kubernetes Deployment with Kustomize

This directory contains Kubernetes manifests for deploying the MLflow KServe Webhook Listener using Kustomize.

## Directory Structure

```
k8s/
├── base/                       # Base manifests (namespace-agnostic)
│   ├── kustomization.yaml
│   ├── rbac.yaml              # ServiceAccount, ClusterRole, ClusterRoleBinding
│   ├── configmap.yaml         # InferenceService template
│   ├── deployment.yaml        # Main deployment
│   ├── service.yaml           # ClusterIP service
│   └── secret.yaml.example    # Example secret configuration
├── overlays/
│   ├── default/               # Default configuration
│   │   ├── kustomization.yaml
│   │   └── deployment-patch.yaml
│   └── examples/              # Cloud-specific examples
│       ├── gcp/
│       ├── aws/
│       └── azure/
└── README.md
```

## Prerequisites

1. **kubectl** (v1.14+) - Kustomize is built into kubectl
2. **Kubernetes cluster** with KServe installed
3. **MLflow tracking server** deployed in your cluster

## Quick Start

### 1. Create the Webhook Secret

First, generate a secure webhook secret and create a Kubernetes secret:

```bash
# Generate a secure random secret
SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Create the secret in the mlflow namespace
kubectl create namespace mlflow
kubectl create secret generic mlflow-webhook-secret \
  --from-literal=secret=$SECRET \
  -n mlflow

# Save this secret - you'll need it to configure MLflow webhooks
echo "Your webhook secret: $SECRET"
```

### 2. Deploy Using the Default Configuration

```bash
# Deploy with default settings
kubectl apply -k k8s/overlays/default/

# Verify deployment
kubectl get pods -n mlflow -l app=mlflow-kserve-webhook-listener
kubectl logs -n mlflow -l app=mlflow-kserve-webhook-listener -f
```

### 3. Verify the Deployment

```bash
# Check the service
kubectl get svc -n mlflow mlflow-kserve-webhook-listener

# Test the health endpoint (from within cluster)
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n mlflow -- \
  curl http://mlflow-kserve-webhook-listener/health
```

## Customization

### Option 1: Using Overlays (Recommended)

Create your own overlay to customize the deployment:

```bash
# Create a new overlay directory
mkdir -p k8s/overlays/production

# Create kustomization.yaml
cat > k8s/overlays/production/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: mlflow-prod

bases:
  - ../../base

patches:
  - path: deployment-patch.yaml
    target:
      kind: Deployment
      name: mlflow-kserve-webhook-listener

images:
  - name: ghcr.io/nebari-dev/mlflow-kserve-webhook-listener
    newTag: v1.0.0
EOF

# Create your deployment patch with custom values
cat > k8s/overlays/production/deployment-patch.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-kserve-webhook-listener
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: listener
        env:
        - name: MLFLOW_KSERVE_MLFLOW_TRACKING_URI
          value: "http://mlflow-server.mlflow-prod.svc.cluster.local:5000"
        - name: MLFLOW_KSERVE_KUBE_NAMESPACE
          value: "kserve-prod-models"
        - name: MLFLOW_KSERVE_STORAGE_URI_BASE
          value: "s3://my-prod-bucket/mlflow"
        # ... add other env vars as needed
EOF

# Deploy your custom overlay
kubectl apply -k k8s/overlays/production/
```

### Option 2: Direct Kustomization Edits

You can edit the overlay files directly:

```bash
# Edit the default overlay
vim k8s/overlays/default/deployment-patch.yaml

# Apply changes
kubectl apply -k k8s/overlays/default/
```

## Configuration Options

### Environment Variables

All configuration is done through environment variables in the deployment patch:

| Variable | Description | Example |
|----------|-------------|---------|
| `MLFLOW_KSERVE_MLFLOW_TRACKING_URI` | MLflow server URL | `http://mlflow-server:5000` |
| `MLFLOW_KSERVE_KUBE_NAMESPACE` | Namespace for InferenceServices | `kserve-models` |
| `MLFLOW_KSERVE_STORAGE_URI_BASE` | Base storage URI | `gs://bucket/path` |
| `MLFLOW_KSERVE_LOG_LEVEL` | Logging level | `INFO`, `DEBUG` |
| `MLFLOW_KSERVE_PREDICTOR_CPU_REQUEST` | CPU request for models | `100m` |
| `MLFLOW_KSERVE_PREDICTOR_MEMORY_REQUEST` | Memory request for models | `512Mi` |

See [deployment-patch.yaml](overlays/default/deployment-patch.yaml) for all available options.

### Namespace Configuration

To deploy in a different namespace:

1. Update the `namespace` field in your overlay's `kustomization.yaml`
2. Create the secret in that namespace
3. Apply: `kubectl apply -k k8s/overlays/your-overlay/`

### Storage Configuration

#### Google Cloud Storage (GCS)
```yaml
- name: MLFLOW_KSERVE_STORAGE_URI_BASE
  value: "gs://your-bucket/mlflow-artifacts"
```

#### AWS S3
```yaml
- name: MLFLOW_KSERVE_STORAGE_URI_BASE
  value: "s3://your-bucket/mlflow-artifacts"
```

#### Azure Blob Storage
```yaml
- name: MLFLOW_KSERVE_STORAGE_URI_BASE
  value: "wasbs://container@account.blob.core.windows.net/mlflow-artifacts"
```

See cloud-specific examples in [k8s/overlays/examples/](overlays/examples/).

## Cloud Provider Examples

### Google Cloud (GCP)

```bash
kubectl apply -k k8s/overlays/examples/gcp/
```

### Amazon Web Services (AWS)

```bash
kubectl apply -k k8s/overlays/examples/aws/
```

### Microsoft Azure

```bash
kubectl apply -k k8s/overlays/examples/azure/
```

## Advanced Topics

### Scaling

To increase replicas:

```yaml
# In your overlay's deployment-patch.yaml
spec:
  replicas: 3
```

### Resource Limits

Adjust the webhook listener pod resources:

```yaml
spec:
  template:
    spec:
      containers:
      - name: listener
        resources:
          requests:
            cpu: 200m
            memory: 512Mi
          limits:
            cpu: 1
            memory: 1Gi
```

### Custom InferenceService Template

To use a custom template:

1. Update the ConfigMap in `k8s/base/configmap.yaml`, or
2. Mount your own ConfigMap and update `MLFLOW_KSERVE_INFERENCE_SERVICE_TEMPLATE`

### Using a Different Image

Update the image in your overlay's `kustomization.yaml`:

```yaml
images:
  - name: ghcr.io/nebari-dev/mlflow-kserve-webhook-listener
    newName: your-registry/mlflow-kserve-webhook-listener
    newTag: your-tag
```

## Troubleshooting

### Check Pod Status
```bash
kubectl get pods -n mlflow -l app=mlflow-kserve-webhook-listener
```

### View Logs
```bash
kubectl logs -n mlflow -l app=mlflow-kserve-webhook-listener -f
```

### Check RBAC Permissions
```bash
# Verify ServiceAccount exists
kubectl get sa -n mlflow mlflow-kserve-webhook-listener

# Verify ClusterRole
kubectl get clusterrole mlflow-kserve-webhook-listener

# Verify ClusterRoleBinding
kubectl get clusterrolebinding mlflow-kserve-webhook-listener
```

### Test Webhook Endpoint
```bash
# Port-forward to test locally
kubectl port-forward -n mlflow svc/mlflow-kserve-webhook-listener 8000:80

# Test in another terminal
curl http://localhost:8000/health
```

### Common Issues

1. **Pod can't create InferenceServices**
   - Check RBAC permissions
   - Verify the ServiceAccount is bound correctly
   - Check target namespace exists

2. **Storage access issues**
   - Verify storage URI format
   - Check cloud credentials (secrets, IAM roles, etc.)
   - Ensure KServe has access to the storage

3. **MLflow connection issues**
   - Verify MLflow server URL is accessible from the pod
   - Check network policies
   - Verify webhook secret matches

## Updating the Deployment

```bash
# After making changes to your overlay
kubectl apply -k k8s/overlays/your-overlay/

# To force a rollout restart
kubectl rollout restart deployment/mlflow-kserve-webhook-listener -n mlflow

# Check rollout status
kubectl rollout status deployment/mlflow-kserve-webhook-listener -n mlflow
```

## Uninstalling

```bash
# Delete using the same overlay you used to deploy
kubectl delete -k k8s/overlays/default/

# Or delete resources individually
kubectl delete deployment mlflow-kserve-webhook-listener -n mlflow
kubectl delete svc mlflow-kserve-webhook-listener -n mlflow
kubectl delete configmap inference-service-template -n mlflow
kubectl delete secret mlflow-webhook-secret -n mlflow
kubectl delete sa mlflow-kserve-webhook-listener -n mlflow
kubectl delete clusterrole mlflow-kserve-webhook-listener
kubectl delete clusterrolebinding mlflow-kserve-webhook-listener
```

## Contributing

When adding new cloud providers or configurations, please:

1. Create a new overlay under `k8s/overlays/examples/`
2. Include a deployment patch with cloud-specific settings
3. Document any cloud-specific prerequisites
4. Update this README with the new example

## Additional Resources

- [Kustomize Documentation](https://kustomize.io/)
- [KServe Documentation](https://kserve.github.io/website/)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
