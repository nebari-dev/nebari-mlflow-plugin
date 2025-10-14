# MLflow to KServe InferenceService Webhook Listener Specification

## Overview

A FastAPI service that listens for MLflow webhook events and automatically manages KServe InferenceService deployments based on model tags. When a model version is tagged with `deploy: true`, the service creates a corresponding InferenceService in the Kubernetes cluster. When the tag is removed or set to any other value, the service deletes the InferenceService.

## Architecture

### Components

1. **FastAPI Web Service** - REST API that receives MLflow webhook events
2. **Kubernetes Client** - Manages InferenceService resources via the Kubernetes API
3. **Configuration Module** - Pydantic Settings for environment-based configuration
4. **Template Engine** - Renders InferenceService YAML from configurable templates (jinja2)

## Functional Requirements

### 1. Webhook Event Handling

#### Supported Events
- `model_version_tag.set` - When a tag is added or updated on a model version
- `model_version_tag.deleted` - When a tag is removed from a model version

#### Event Processing Logic
```
IF event == "model_version_tag.set" AND tag_key == "deploy":
  IF tag_value == "true":
    - Fetch model version details from MLflow
    - Render InferenceService manifest from template
    - Create or update InferenceService in Kubernetes
  ELSE:
    - Delete InferenceService if it exists

IF event == "model_version_tag.deleted" AND tag_key == "deploy":
  - Delete InferenceService if it exists
```

### 2. InferenceService Management

#### Naming Convention
- **InferenceService name**: `mlflow-{model_name}-v{version}` (sanitized for K8s naming rules)
- **Namespace**: Configurable via settings (default: `kserve-mlflow-models`)

#### Template Variables
The InferenceService template should support the following variables:
- `{name}` - Generated InferenceService name
- `{namespace}` - Target namespace
- `{model_name}` - MLflow model name
- `{model_version}` - MLflow model version
- `{storage_uri}` - Full path to model artifacts
- `{run_id}` - MLflow run ID
- `{experiment_id}` - MLflow experiment ID

#### InferenceService Template Structure
```yaml
apiVersion: "serving.kserve.io/v1beta1"
kind: "InferenceService"
metadata:
  name: "{name}"
  namespace: "{namespace}"
  labels:
    mlflow.model: "{model_name}"
    mlflow.version: "{model_version}"
    mlflow.run-id: "{run_id}"
spec:
  predictor:
    model:
      modelFormat:
        name: mlflow
      protocolVersion: v2
      storageUri: "{storage_uri}"
```

### 3. Configuration Management

#### Pydantic Settings Schema

```python
class Settings(BaseSettings):
    # FastAPI Server
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # MLflow Configuration
    mlflow_tracking_uri: str  # Required
    mlflow_webhook_secret: str  # Required

    # Kubernetes Configuration
    kube_namespace: str = "kserve-mlflow-models"
    kube_in_cluster: bool = True  # Use in-cluster config

    # InferenceService Configuration
    inference_service_template: str  # Path to template file or inline YAML
    storage_uri_base: str  # Base URI for model storage (e.g., "gs://bucket-name")

    # Optional: Resource limits
    predictor_cpu_request: str = "100m"
    predictor_cpu_limit: str = "1"
    predictor_memory_request: str = "512Mi"
    predictor_memory_limit: str = "2Gi"

    # Logging
    log_level: str = "INFO"

    class Config:
        env_prefix = "MLFLOW_KSERVE_"
        case_sensitive = False
```

#### Environment Variables
All settings can be configured via environment variables with the prefix `MLFLOW_KSERVE_`:
- `MLFLOW_KSERVE_MLFLOW_TRACKING_URI`
- `MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET`
- `MLFLOW_KSERVE_KUBE_NAMESPACE`
- etc.

## API Endpoints

### POST /webhook
Receives MLflow webhook events.

**Headers:**
- `x-mlflow-signature` - HMAC signature for verification
- `x-mlflow-delivery-id` - Unique delivery identifier
- `x-mlflow-timestamp` - Timestamp of the event

**Request Body:**
```json
{
  "entity": "model_version_tag",
  "action": "set",
  "timestamp": 1234567890,
  "data": {
    "name": "iris-classifier",
    "version": "3",
    "key": "deploy",
    "value": "true",
    "run_id": "487892dfbe01444bbe535773ee32b14c",
    "experiment_id": "1"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "action": "created",
  "inference_service": "mlflow-iris-classifier-v3",
  "namespace": "kserve-mlflow-models"
}
```

### GET /health
Health check endpoint for Kubernetes liveness/readiness probes.

**Response:**
```json
{
  "status": "healthy",
  "mlflow_connected": true,
  "kubernetes_connected": true
}
```

### GET /services
List all managed InferenceServices (optional, for debugging).

**Response:**
```json
{
  "services": [
    {
      "name": "mlflow-iris-classifier-v3",
      "namespace": "kserve-mlflow-models",
      "model_name": "iris-classifier",
      "model_version": "3",
      "status": "Ready"
    }
  ]
}
```

## Kubernetes Deployment Specifications

### Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-kserve-webhook-listener
  namespace: mlflow
  labels:
    app: mlflow-kserve-webhook-listener
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mlflow-kserve-webhook-listener
  template:
    metadata:
      labels:
        app: mlflow-kserve-webhook-listener
    spec:
      serviceAccountName: mlflow-kserve-webhook-listener
      containers:
      - name: listener
        image: ghcr.io/nebari-dev/mlflow-kserve-webhook-listener:latest
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: MLFLOW_KSERVE_MLFLOW_TRACKING_URI
          value: "http://mlflow-server:5000"
        - name: MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET
          valueFrom:
            secretKeyRef:
              name: mlflow-webhook-secret
              key: secret
        - name: MLFLOW_KSERVE_KUBE_NAMESPACE
          value: "kserve-mlflow-models"
        - name: MLFLOW_KSERVE_STORAGE_URI_BASE
          value: "gs://nebari-mlflow-artifacts"
        - name: MLFLOW_KSERVE_KUBE_IN_CLUSTER
          value: "true"
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
```

### Service Manifest

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mlflow-kserve-webhook-listener
  namespace: mlflow
spec:
  selector:
    app: mlflow-kserve-webhook-listener
  ports:
  - port: 80
    targetPort: http
    protocol: TCP
    name: http
  type: ClusterIP
```

### ServiceAccount and RBAC

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: mlflow-kserve-webhook-listener
  namespace: mlflow
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: mlflow-kserve-webhook-listener
rules:
- apiGroups: ["serving.kserve.io"]
  resources: ["inferenceservices"]
  verbs: ["get", "list", "create", "update", "patch", "delete"]
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: mlflow-kserve-webhook-listener
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: mlflow-kserve-webhook-listener
subjects:
- kind: ServiceAccount
  name: mlflow-kserve-webhook-listener
  namespace: mlflow
```

### ConfigMap for Template

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: inference-service-template
  namespace: mlflow
data:
  template.yaml: |
    apiVersion: "serving.kserve.io/v1beta1"
    kind: "InferenceService"
    metadata:
      name: "{name}"
      namespace: "{namespace}"
      labels:
        mlflow.model: "{model_name}"
        mlflow.version: "{model_version}"
        mlflow.run-id: "{run_id}"
        managed-by: "mlflow-kserve-webhook-listener"
    spec:
      predictor:
        model:
          modelFormat:
            name: mlflow
          protocolVersion: v2
          storageUri: "{storage_uri}"
```

## References
- docker-compose dir may have some useful stuff already in it
- inference-service-test dir may also have some useful stuff already in it

## Error Handling

### Scenarios

1. **Invalid Webhook Signature**
   - Response: 401 Unauthorized
   - Action: Log warning, do not process event

2. **Kubernetes API Error**
   - Response: 500 Internal Server Error
   - Action: Log error with details, return error to MLflow for retry

3. **MLflow API Error**
   - Response: 502 Bad Gateway
   - Action: Log error, attempt to proceed with available data

4. **Invalid Template**
   - Response: 500 Internal Server Error
   - Action: Log error, return failure

5. **InferenceService Already Exists**
   - Response: 200 OK
   - Action: Update existing InferenceService with new configuration

6. **InferenceService Not Found for Deletion**
   - Response: 200 OK
   - Action: Log info, treat as successful (idempotent)

## Security Considerations

1. **Webhook Authentication**
   - Verify HMAC signature on all incoming webhooks
   - Validate timestamp to prevent replay attacks (5-minute window)

2. **Kubernetes RBAC**
   - Minimal permissions: only manage InferenceServices in designated namespace
   - Use ServiceAccount with explicit RBAC rules

3. **Secret Management**
   - Store webhook secret in Kubernetes Secret
   - Never log sensitive information

4. **Network Policies**
   - Restrict ingress to webhook endpoint
   - Allow egress to MLflow server and Kubernetes API only

## Monitoring and Observability

### Metrics (Prometheus-compatible)
- `webhook_events_total{entity, action}` - Counter of webhook events
- `inference_service_operations_total{operation, status}` - Counter of K8s operations
- `webhook_processing_duration_seconds` - Histogram of processing time
- `mlflow_api_errors_total` - Counter of MLflow API errors
- `kubernetes_api_errors_total` - Counter of K8s API errors

### Logs
- Structured JSON logging
- Include correlation ID (delivery ID from webhook)
- Log levels: DEBUG, INFO, WARNING, ERROR

### Health Checks
- `/health` endpoint returns:
  - MLflow connectivity status
  - Kubernetes API connectivity status
  - Overall service health

## Development Workflow

### Directory Structure
```
webhook-listener/
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Pydantic settings
│   ├── kubernetes_client.py    # K8s client wrapper
│   ├── mlflow_client.py        # MLflow API client
│   ├── webhook_handler.py      # Webhook processing logic
│   └── templates.py            # Template rendering
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── rbac.yaml
│   └── configmap.yaml
├── tests/
│   ├── test_webhook_handler.py
│   ├── test_kubernetes_client.py
│   └── test_templates.py
├── Dockerfile
├── pyproject.toml
└── README.md
```

### Dependencies
```toml
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.0.0",
  "pydantic-settings>=2.0.0",
  "kubernetes>=29.0.0",
  "mlflow>=3.2.0",
  "jinja2>=3.1.0",
  "pyyaml>=6.0",
  "httpx>=0.27.0",
]
```

## Testing Strategy

### Unit Tests
- Webhook signature verification
- Template rendering with various inputs
- Kubernetes resource name sanitization
- Configuration validation

### Integration Tests
- Mock MLflow webhook events
- Mock Kubernetes API responses
- End-to-end event processing

### Manual Testing
1. Deploy service to development cluster
2. Register MLflow webhook pointing to service
3. Create test model and set `deploy: true` tag
4. Verify InferenceService is created
5. Change tag to `deploy: false`
6. Verify InferenceService is deleted

## Future Enhancements

1. **Multi-namespace Support** - Deploy to different namespaces based on model metadata
2. **Advanced Templating** - Support for custom predictor configurations per model
3. **Rollback Support** - Detect failed deployments and revert to previous version
4. **Canary Deployments** - Support for gradual rollouts with traffic splitting
5. **Model Registry Integration** - Sync model metadata to Kubernetes labels/annotations
6. **Metrics Integration** - Expose model performance metrics from InferenceService
7. **Alerting** - Integration with Prometheus Alertmanager for deployment failures

---

## Implementation Task List

This task list provides an ordered approach to implementing the service, starting with stubs/dummy implementations to establish the overall flow, then filling in the details.

### Phase 1: Project Setup & Structure (Skeleton with Stubs)

**Goal:** Create the directory structure and stub out all modules with dummy implementations to verify the overall architecture flows correctly.

- [x] **1.1** Create directory structure
  ```
  webhook-listener/src/
  webhook-listener/k8s/
  webhook-listener/tests/
  ```

- [x] **1.2** Update `pyproject.toml` with dependencies
  - Add: fastapi, uvicorn, pydantic, pydantic-settings, kubernetes, mlflow, jinja2, pyyaml, httpx
  - Add dev dependencies: pytest, pytest-asyncio, pytest-mock

- [x] **1.3** Create `src/config.py` with Pydantic Settings
  - Define complete `Settings` class with all configuration fields
  - Add environment variable loading with `MLFLOW_KSERVE_` prefix
  - Include validation for required fields

- [x] **1.4** Create `src/main.py` with FastAPI application skeleton
  - Initialize FastAPI app
  - Add dummy endpoints: `POST /webhook`, `GET /health`, `GET /services`
  - Each endpoint returns placeholder responses
  - Add startup/shutdown event handlers (empty for now)

- [x] **1.5** Create stub modules with dummy functions:
  - `src/webhook_handler.py`:
    - `verify_mlflow_signature()` → returns `True` (stub)
    - `process_webhook_event()` → logs event, returns success (stub)
  - `src/kubernetes_client.py`:
    - `class KubernetesClient` with methods:
      - `create_inference_service()` → logs, returns success (stub)
      - `delete_inference_service()` → logs, returns success (stub)
      - `get_inference_service()` → returns None (stub)
      - `list_inference_services()` → returns empty list (stub)
  - `src/mlflow_client.py`:
    - `class MLflowClient` with methods:
      - `get_model_version()` → returns dummy model data (stub)
      - `get_run()` → returns dummy run data (stub)
  - `src/templates.py`:
    - `render_inference_service()` → returns dummy YAML string (stub)
    - `sanitize_k8s_name()` → returns input lowercased (stub)

- [x] **1.6** Test the skeleton
  - Run `uvicorn src.main:app --reload`
  - Verify all endpoints respond (even with dummy data)
  - Send test POST to `/webhook` with sample payload
  - Verify logging works and flow is correct

### Phase 2: Configuration & Template System

**Goal:** Implement real configuration loading and template rendering.

- [ ] **2.1** Implement complete Pydantic Settings in `src/config.py`
  - Add field validation (e.g., URL validation, required fields)
  - Test loading from environment variables
  - Add `model_config` for proper env prefix handling

- [x] **2.2** Create default InferenceService template
  - Create `templates/inference_service.yaml.j2` with Jinja2 template
  - Include all template variables: name, namespace, model_name, model_version, storage_uri, run_id, experiment_id
  - Add labels for tracking

- [x] **2.3** Implement `src/templates.py`
  - `render_inference_service()`: Load and render Jinja2 template
  - `sanitize_k8s_name()`: Implement K8s naming rules (lowercase, max 253 chars, alphanumeric + hyphens)
  - `generate_inference_service_name()`: Create name from model_name and version
  - Add error handling for template rendering failures

- [x] **2.4** Test template rendering independently
  - Unit tests for `sanitize_k8s_name()` with various inputs
  - Unit tests for template rendering with sample data
  - Verify generated YAML is valid

### Phase 3: Webhook Verification & Event Processing

**Goal:** Implement webhook signature verification and event routing logic.

- [x] **3.1** Implement signature verification in `src/webhook_handler.py`
  - `verify_timestamp_freshness()`: Check timestamp is within 5 minutes
  - `verify_mlflow_signature()`: Implement HMAC-SHA256 verification
  - Add comprehensive logging for security events

- [x] **3.2** Implement event routing logic in `src/webhook_handler.py`
  - `process_webhook_event()`: Main orchestrator function
  - Parse webhook payload and extract relevant fields
  - Route to appropriate handler based on entity and action:
    - `handle_tag_set_event()`: When tag is set
    - `handle_tag_deleted_event()`: When tag is deleted
  - Add logic to check if tag_key == "deploy"

- [ ] **3.3** Update `src/main.py` webhook endpoint
  - Wire up signature verification (reject if invalid)
  - Call `process_webhook_event()` with verified payload
  - Return appropriate HTTP status codes and responses
  - Add error handling with proper status codes (401, 500, 502)

- [ ] **3.4** Test webhook endpoint
  - Unit tests for signature verification (valid/invalid cases)
  - Unit tests for event routing logic
  - Mock webhook requests with proper headers

### Phase 4: MLflow Integration

**Goal:** Implement MLflow API client to fetch model details.

- [ ] **4.1** Implement `src/mlflow_client.py`
  - `MLflowClient.__init__()`: Initialize with tracking URI from settings
  - `get_model_version()`: Fetch model version details including run_id
  - `get_run()`: Fetch run details to get artifact URI
  - `build_storage_uri()`: Construct full storage URI for model artifacts
  - Add error handling for MLflow API failures

- [ ] **4.2** Integrate MLflow client into webhook handler
  - In `handle_tag_set_event()`, call MLflow to get model details
  - Extract: model_name, model_version, run_id, experiment_id, storage_uri
  - Pass this data to template renderer

- [ ] **4.3** Test MLflow integration
  - Unit tests with mocked MLflow responses
  - Test error handling (MLflow unavailable, model not found)

### Phase 5: Kubernetes Integration

**Goal:** Implement Kubernetes client to manage InferenceServices.

- [ ] **5.1** Implement `src/kubernetes_client.py`
  - `KubernetesClient.__init__()`: Initialize K8s client (in-cluster or local)
  - `create_inference_service()`: Create InferenceService from YAML manifest
  - `delete_inference_service()`: Delete InferenceService by name
  - `get_inference_service()`: Get InferenceService status
  - `list_inference_services()`: List all InferenceServices with mlflow labels
  - `update_inference_service()`: Update existing InferenceService
  - Add error handling for K8s API failures

- [ ] **5.2** Wire up Kubernetes client in webhook handler
  - In `handle_tag_set_event()`:
    - Check if tag_value == "true"
    - If yes: render template + create/update InferenceService
    - If no: delete InferenceService
  - In `handle_tag_deleted_event()`:
    - Delete InferenceService

- [ ] **5.3** Test Kubernetes integration
  - Unit tests with mocked K8s client
  - Test create/update/delete operations
  - Test idempotency (delete non-existent service should succeed)

### Phase 6: Health Checks & Observability

**Goal:** Implement health checks and basic observability.

- [ ] **6.1** Implement health check in `src/main.py`
  - Test MLflow connectivity (simple API call)
  - Test Kubernetes API connectivity
  - Return detailed status for each component

- [ ] **6.2** Implement `/services` endpoint
  - List all managed InferenceServices
  - Return service details with status

- [ ] **6.3** Add structured logging
  - Configure logging with JSON formatter
  - Add correlation IDs (use delivery ID from webhook)
  - Log key events: webhook received, signature verified, K8s operations

- [ ] **6.4** Add basic error handling middleware
  - Catch unhandled exceptions
  - Return proper error responses
  - Log errors with full context

### Phase 7: Kubernetes Manifests

**Goal:** Create K8s manifests to deploy the service.

- [ ] **7.1** Create `k8s/rbac.yaml`
  - ServiceAccount
  - ClusterRole with InferenceService permissions
  - ClusterRoleBinding

- [ ] **7.2** Create `k8s/configmap.yaml`
  - Store InferenceService template

- [ ] **7.3** Create `k8s/deployment.yaml`
  - Deployment with proper env vars
  - Resource limits
  - Health check probes
  - Volume mount for ConfigMap template

- [ ] **7.4** Create `k8s/service.yaml`
  - ClusterIP service exposing port 80

- [ ] **7.5** Create `k8s/secret.yaml.example`
  - Example secret for webhook secret
  - Add instructions in README

### Phase 8: Containerization

**Goal:** Create Docker image for deployment.

- [ ] **8.1** Create `Dockerfile`
  - Multi-stage build for smaller image
  - Install dependencies
  - Copy source code
  - Set entrypoint to uvicorn

- [ ] **8.2** Create `.dockerignore`
  - Exclude tests, cache, etc.

- [ ] **8.3** Test Docker build and run locally

### Phase 9: Testing & Documentation

**Goal:** Add comprehensive tests and documentation.

- [ ] **9.1** Write unit tests
  - `tests/test_config.py`: Test configuration loading
  - `tests/test_templates.py`: Test template rendering and name sanitization
  - `tests/test_webhook_handler.py`: Test signature verification and event routing
  - `tests/test_kubernetes_client.py`: Test K8s operations (mocked)
  - `tests/test_mlflow_client.py`: Test MLflow API calls (mocked)

- [ ] **9.2** Write integration tests
  - `tests/test_integration.py`: End-to-end webhook processing with mocks

- [ ] **9.3** Create `README.md`
  - Overview
  - Setup instructions
  - Configuration documentation
  - Deployment instructions
  - Testing instructions

- [ ] **9.4** Create example configurations
  - `.env.example`: Example environment variables
  - Example webhook payload for testing

### Phase 10: End-to-End Testing

**Goal:** Deploy and test in a real environment.

- [ ] **10.1** Deploy to development cluster
  - Apply K8s manifests
  - Verify pod starts and is healthy

- [ ] **10.2** Configure MLflow webhook
  - Create webhook pointing to service
  - Set webhook secret

- [ ] **10.3** Manual end-to-end test
  - Create test model in MLflow
  - Set `deploy: true` tag
  - Verify InferenceService is created in K8s
  - Test inference endpoint
  - Change tag to `deploy: false`
  - Verify InferenceService is deleted

- [ ] **10.4** Load testing (optional)
  - Test with multiple concurrent webhooks
  - Verify no race conditions

---

## Implementation Tips

1. **Start Simple**: Focus on getting the skeleton running first with dummy implementations. This helps validate the architecture early.

2. **Test Incrementally**: After each phase, run the application and test the newly implemented functionality.

3. **Use Mocks**: For Phases 1-6, use mocks or local testing. You don't need a real K8s cluster until Phase 10.

4. **Logging First**: Add detailed logging from the start. It's crucial for debugging webhook processing.

5. **Error Handling**: Add try-except blocks and proper error responses as you implement each component.

6. **Configuration**: Use `.env` file for local development to avoid hardcoding values.
