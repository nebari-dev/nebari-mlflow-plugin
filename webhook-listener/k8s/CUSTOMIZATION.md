# Customization Guide

This document explains how to customize the Kubernetes deployment for different environments using Kustomize.

## Understanding the Structure

### Base Layer (`k8s/base/`)
Contains namespace-agnostic, environment-agnostic manifests:
- **No hardcoded namespaces** - Set by overlays
- **No hardcoded configuration** - Defined in overlays
- **Minimal environment variables** - Patched by overlays

### Overlay Layer (`k8s/overlays/`)
Contains environment-specific customizations:
- **Namespace selection**
- **Environment variables**
- **Image tags**
- **Resource limits**
- **Storage configuration**

## Common Customization Scenarios

### 1. Change Deployment Namespace

Edit your overlay's `kustomization.yaml`:

```yaml
namespace: my-custom-namespace  # Change this line
```

That's it! Kustomize will automatically:
- Place all resources in `my-custom-namespace`
- Update the ClusterRoleBinding to reference the correct namespace
- Ensure the ServiceAccount references are correct

### 2. Change MLflow Server Location

Edit your overlay's `deployment-patch.yaml`:

```yaml
- name: MLFLOW_KSERVE_MLFLOW_TRACKING_URI
  value: "http://mlflow-server.different-namespace.svc.cluster.local:5000"
```

### 3. Change Target Namespace for InferenceServices

Edit your overlay's `deployment-patch.yaml`:

```yaml
- name: MLFLOW_KSERVE_KUBE_NAMESPACE
  value: "my-kserve-namespace"
```

### 4. Change Storage Backend

#### From GCS to S3:
```yaml
- name: MLFLOW_KSERVE_STORAGE_URI_BASE
  value: "s3://my-bucket/mlflow-artifacts"
```

#### From S3 to Azure:
```yaml
- name: MLFLOW_KSERVE_STORAGE_URI_BASE
  value: "wasbs://container@account.blob.core.windows.net/mlflow"
```

### 5. Change Image Version

Edit your overlay's `kustomization.yaml`:

```yaml
images:
  - name: ghcr.io/nebari-dev/mlflow-kserve-webhook-listener
    newTag: v1.2.3  # Specify your version
```

Or use a different registry:

```yaml
images:
  - name: ghcr.io/nebari-dev/mlflow-kserve-webhook-listener
    newName: my-registry.io/mlflow-webhook-listener
    newTag: v1.2.3
```

### 6. Adjust Resource Limits

#### For the webhook listener pod:

Create a new patch file `k8s/overlays/my-env/resources-patch.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-kserve-webhook-listener
spec:
  template:
    spec:
      containers:
      - name: listener
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2
            memory: 2Gi
```

Reference it in `kustomization.yaml`:

```yaml
patches:
  - path: deployment-patch.yaml
  - path: resources-patch.yaml
```

#### For created InferenceServices:

Edit the environment variables in `deployment-patch.yaml`:

```yaml
- name: MLFLOW_KSERVE_PREDICTOR_CPU_REQUEST
  value: "500m"
- name: MLFLOW_KSERVE_PREDICTOR_CPU_LIMIT
  value: "4"
- name: MLFLOW_KSERVE_PREDICTOR_MEMORY_REQUEST
  value: "1Gi"
- name: MLFLOW_KSERVE_PREDICTOR_MEMORY_LIMIT
  value: "8Gi"
```

### 7. Scale Replicas

Add to your overlay's `kustomization.yaml`:

```yaml
replicas:
  - name: mlflow-kserve-webhook-listener
    count: 3
```

Or in a patch:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-kserve-webhook-listener
spec:
  replicas: 3
```

### 8. Enable Debug Logging

Edit your overlay's `deployment-patch.yaml`:

```yaml
- name: MLFLOW_KSERVE_LOG_LEVEL
  value: "DEBUG"
```

## Creating a New Environment

Let's create a production environment as an example:

```bash
# 1. Create directory structure
mkdir -p k8s/overlays/production

# 2. Create kustomization.yaml
cat > k8s/overlays/production/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: mlflow-production

resources:
  - ../../base

patches:
  - path: deployment-patch.yaml
    target:
      kind: Deployment
      name: mlflow-kserve-webhook-listener

images:
  - name: ghcr.io/nebari-dev/mlflow-kserve-webhook-listener
    newTag: v1.0.0  # Use specific version in production

replicas:
  - name: mlflow-kserve-webhook-listener
    count: 3  # High availability
EOF

# 3. Create deployment patch
cat > k8s/overlays/production/deployment-patch.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-kserve-webhook-listener
spec:
  template:
    spec:
      containers:
      - name: listener
        env:
        # Production MLflow server
        - name: MLFLOW_KSERVE_MLFLOW_TRACKING_URI
          value: "http://mlflow-server.mlflow-production.svc.cluster.local:5000"

        # Production namespace for models
        - name: MLFLOW_KSERVE_KUBE_NAMESPACE
          value: "kserve-production"

        # Production storage
        - name: MLFLOW_KSERVE_STORAGE_URI_BASE
          value: "s3://prod-mlflow-bucket/artifacts"

        # Higher resources for production
        - name: MLFLOW_KSERVE_PREDICTOR_CPU_REQUEST
          value: "500m"
        - name: MLFLOW_KSERVE_PREDICTOR_CPU_LIMIT
          value: "4"
        - name: MLFLOW_KSERVE_PREDICTOR_MEMORY_REQUEST
          value: "1Gi"
        - name: MLFLOW_KSERVE_PREDICTOR_MEMORY_LIMIT
          value: "8Gi"

        # Production logging
        - name: MLFLOW_KSERVE_LOG_LEVEL
          value: "INFO"

        # Webhook secret
        - name: MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET
          valueFrom:
            secretKeyRef:
              name: mlflow-webhook-secret-prod
              key: secret

        # Required vars
        - name: MLFLOW_KSERVE_KUBE_IN_CLUSTER
          value: "true"
        - name: MLFLOW_KSERVE_INFERENCE_SERVICE_TEMPLATE
          value: "/etc/templates/template.yaml"
        - name: MLFLOW_KSERVE_APP_HOST
          value: "0.0.0.0"
        - name: MLFLOW_KSERVE_APP_PORT
          value: "8000"

        resources:
          requests:
            cpu: 200m
            memory: 512Mi
          limits:
            cpu: 1
            memory: 1Gi
EOF

# 4. Deploy
kubectl create secret generic mlflow-webhook-secret-prod \
  --from-literal=secret=your-prod-secret \
  -n mlflow-production

kubectl apply -k k8s/overlays/production/
```

## Best Practices

### 1. **Version Control**
- Commit base manifests to git
- Commit overlay structure to git
- **DO NOT** commit secrets or sensitive values

### 2. **Environment Separation**
```
k8s/overlays/
├── dev/          # Development environment
├── staging/      # Staging environment
└── production/   # Production environment
```

### 3. **Secret Management**
- Use external secret management (e.g., Sealed Secrets, External Secrets Operator)
- Never commit actual secrets
- Use different secrets per environment

### 4. **Testing**
```bash
# Always test kustomize build before applying
kubectl kustomize k8s/overlays/my-env/ > /tmp/test.yaml
kubectl apply --dry-run=client -f /tmp/test.yaml
```

### 5. **Image Tags**
- Development: Use `latest` or `main` tags
- Staging: Use specific version tags (e.g., `v1.2.3-rc1`)
- Production: Use immutable version tags (e.g., `v1.2.3`)

## Matrix of Configuration Options

| Setting | Environment Variable | Default | Common Values |
|---------|---------------------|---------|---------------|
| Namespace | `namespace` in kustomization.yaml | `mlflow` | Any valid namespace |
| MLflow Server | `MLFLOW_KSERVE_MLFLOW_TRACKING_URI` | `http://mlflow-server:5000` | Any HTTP URL |
| Target Namespace | `MLFLOW_KSERVE_KUBE_NAMESPACE` | `kserve-mlflow-models` | Any namespace |
| Storage Base | `MLFLOW_KSERVE_STORAGE_URI_BASE` | `gs://...` | `s3://`, `gs://`, `wasbs://` |
| Image Tag | `newTag` in images | `latest` | Version tags |
| Replicas | `replicas` | 1 | 1-5 typical |
| CPU Request | Pod resources | `100m` | `100m`-`2` |
| Memory Request | Pod resources | `256Mi` | `256Mi`-`4Gi` |
| Model CPU | `MLFLOW_KSERVE_PREDICTOR_CPU_REQUEST` | `100m` | `100m`-`8` |
| Model Memory | `MLFLOW_KSERVE_PREDICTOR_MEMORY_REQUEST` | `512Mi` | `512Mi`-`16Gi` |
| Log Level | `MLFLOW_KSERVE_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` |

## Troubleshooting Customizations

### Build Fails
```bash
# Check syntax
kubectl kustomize k8s/overlays/my-env/

# Validate output
kubectl kustomize k8s/overlays/my-env/ | kubectl apply --dry-run=client -f -
```

### Namespace Issues
- Ensure namespace exists: `kubectl create namespace my-namespace`
- Check ClusterRoleBinding has correct namespace in subjects
- Verify secret is in the same namespace

### Patch Not Applied
- Ensure patch targets correct resource name
- Check patch path is correct in kustomization.yaml
- Verify YAML indentation is correct

### Environment Variables Not Set
- Check strategic merge behavior - arrays are replaced, not merged
- Ensure all required env vars are in your patch
- View final output: `kubectl kustomize k8s/overlays/my-env/ | grep -A 50 "env:"`

## Advanced: Multiple Patches

You can apply multiple patches for organization:

```yaml
# kustomization.yaml
patches:
  - path: namespace-config.yaml  # Namespace-specific settings
  - path: storage-config.yaml    # Storage settings
  - path: resources.yaml         # Resource limits
  - path: scaling.yaml           # Replicas and autoscaling
```

Each patch file only needs to contain the fields you want to change.
