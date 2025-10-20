# KServe Models Web App Deployment

This directory contains the deployment configuration for the KServe Models Web App, a web interface for managing KServe InferenceServices.

## Overview

The models web app provides a user-friendly interface to:
- View all InferenceServices across namespaces
- Create new InferenceServices
- Delete and manage existing InferenceServices
- View metrics via Grafana dashboards (if configured)

## Architecture

The deployment is configured with:
- **Namespace**: `prod`
- **Authentication**: Traefik forward-auth (same as MLflow)
- **URL Path**: `https://nebari.openteams.ai/models/`
- **Internal Service**: ClusterIP on port 80

## Directory Structure

```
models-web-app/
├── README.md                          # This file
└── models-web-app/
    └── config/
        ├── base/                      # Base Kubernetes manifests
        │   ├── deployment.yaml        # Web app deployment
        │   ├── service.yaml           # ClusterIP service
        │   ├── rbac.yaml              # ServiceAccount and RBAC
        │   ├── istio.yaml             # Istio VirtualService (not used)
        │   └── kustomization.yaml     # Base kustomization
        └── overlays/
            └── local/                 # Local deployment configuration
                ├── kustomization.yaml # Main kustomization file
                ├── middleware.yaml    # Traefik middlewares
                └── ingressroute.yaml  # Traefik IngressRoute
```

## Deployment

### Prerequisites

- Kubernetes cluster with:
  - Traefik ingress controller (monitoring `prod` namespace)
  - Forward-auth service running at `forwardauth-service.prod.svc.cluster.local:4181`
  - KServe and Knative Serving installed
  - Istio service mesh

### Deploy the Application

From the `models-web-app/models-web-app` directory:

```bash
cd models-web-app/models-web-app
kustomize build config/overlays/local | kubectl apply -f -
```

This single command deploys:
- ServiceAccount and ClusterRole with permissions to manage InferenceServices
- Deployment with 1 replica
- ClusterIP Service
- Traefik Middlewares (forward-auth, add-slash, stripprefix)
- Traefik IngressRoute

### Verify Deployment

Check that all resources are running:

```bash
# Check deployment status
kubectl get deployment kserve-models-web-app -n prod

# Check pod status
kubectl get pods -n prod -l app.kubernetes.io/component=kserve-models-web-app

# Check service
kubectl get svc kserve-models-web-app -n prod

# Check Traefik resources
kubectl get ingressroute,middleware -n prod | grep kserve
```

Wait for the pod to be ready:

```bash
kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=kserve-models-web-app -n prod --timeout=60s
```

## Configuration

### Environment Variables

The application is configured via ConfigMap with the following settings:

- `APP_PREFIX=/models` - Serves the app at the `/models` URL path
- `APP_DISABLE_AUTH="True"` - Disables internal auth (relies on Traefik forward-auth)
- `APP_SECURE_COOKIES="False"` - Allows cookies over HTTP (internal traffic)
- `GRAFANA_PREFIX="/grafana"` - Grafana dashboard prefix
- `GRAFANA_CPU_MEMORY_DB` - Grafana CPU/memory metrics dashboard
- `GRAFANA_HTTP_REQUESTS_DB` - Grafana HTTP requests dashboard

### Traefik Routing

Traffic flows through the following chain:

1. **User Request**: `https://nebari.openteams.ai/models`
2. **Traefik Ingress**: Matches host and path prefix
3. **Forward-Auth Middleware**: Validates authentication via forward-auth service
4. **Add-Slash Middleware**: Redirects `/models` → `/models/`
5. **Strip-Prefix Middleware**: Removes `/models/` from path
6. **Service**: Routes to `kserve-models-web-app.prod.svc.cluster.local:80`
7. **Application**: Receives request at root path `/`

### RBAC Permissions

The web app has ClusterRole permissions to:
- Create SubjectAccessReviews (authorization checks)
- List and get namespaces, pods, pod logs, and events
- Full CRUD operations on InferenceServices
- Read-only access to Knative Serving resources (services, routes, configurations, revisions)

## Access

### Web Interface

Access the application at: **https://nebari.openteams.ai/models/**

Users will be authenticated via the forward-auth service before accessing the interface.

### Port-Forwarding (Development)

For local development without going through Traefik:

```bash
kubectl port-forward -n prod svc/kserve-models-web-app 5000:80
```

Then access at: **http://localhost:5000/**

Note: When using port-forward, the app expects to be at the root path `/`, so you may need to temporarily change `APP_PREFIX` to `/` in the ConfigMap.

## Customization

### Change the URL Path

To serve the app at a different path (e.g., `/kserve-models`):

1. Update `APP_PREFIX` in [config/overlays/local/kustomization.yaml](models-web-app/config/overlays/local/kustomization.yaml)
2. Update the regex and prefix in [config/overlays/local/middleware.yaml](models-web-app/config/overlays/local/middleware.yaml)
3. Update the path match in [config/overlays/local/ingressroute.yaml](models-web-app/config/overlays/local/ingressroute.yaml)
4. Redeploy: `kustomize build config/overlays/local | kubectl apply -f -`

### Change the Hostname

To use a different hostname:

1. Update the `Host()` match in [config/overlays/local/ingressroute.yaml](models-web-app/config/overlays/local/ingressroute.yaml)
2. Update the regex in [config/overlays/local/middleware.yaml](models-web-app/config/overlays/local/middleware.yaml)
3. Redeploy: `kustomize build config/overlays/local | kubectl apply -f -`

### Change the Namespace

To deploy to a different namespace:

1. Update `namespace:` in [config/overlays/local/kustomization.yaml](models-web-app/config/overlays/local/kustomization.yaml)
2. Ensure Traefik is monitoring that namespace for IngressRoutes
3. Update middleware namespace references in [config/overlays/local/ingressroute.yaml](models-web-app/config/overlays/local/ingressroute.yaml)
4. Redeploy: `kustomize build config/overlays/local | kubectl apply -f -`

## Troubleshooting

### Pod not starting

Check pod logs:
```bash
kubectl logs -n prod -l app.kubernetes.io/component=kserve-models-web-app
```

### Authentication not working

Verify forward-auth service is running:
```bash
kubectl get svc forwardauth-service -n prod
kubectl get pods -n prod -l app=forwardauth-pod
```

Check middleware configuration:
```bash
kubectl get middleware kserve-models-web-app-forward-auth -n prod -o yaml
```

### 404 errors or path issues

Check IngressRoute configuration:
```bash
kubectl get ingressroute kserve-models-web-app-ingressroute -n prod -o yaml
```

Verify the `APP_PREFIX` matches your URL path:
```bash
kubectl get configmap -n prod -l kustomize.component=kserve-models-web-app -o yaml
```

### InferenceServices not visible

Check RBAC permissions:
```bash
kubectl get clusterrole kserve-models-web-app-cluster-role -o yaml
kubectl get clusterrolebinding kserve-models-web-app-binding -o yaml
```

Verify the ServiceAccount is properly bound:
```bash
kubectl get serviceaccount kserve-models-web-app -n prod
```

## Updating the Deployment

To update the configuration:

1. Modify files in `config/overlays/local/`
2. Preview changes: `kustomize build config/overlays/local`
3. Apply changes: `kustomize build config/overlays/local | kubectl apply -f -`
4. Watch rollout: `kubectl rollout status deployment/kserve-models-web-app -n prod`

To update the image version:

Edit `newTag` in `config/overlays/local/kustomization.yaml` or `config/base/kustomization.yaml`, then redeploy.

## Uninstalling

To remove the deployment:

```bash
kustomize build config/overlays/local | kubectl delete -f -
```

Note: This will also delete the ClusterRole and ClusterRoleBinding.

## References

- [KServe Documentation](https://kserve.github.io/website/)
- [KServe Models Web App GitHub](https://github.com/kserve/models-web-app)
- [Traefik IngressRoute Documentation](https://doc.traefik.io/traefik/routing/providers/kubernetes-crd/)
- [Kustomize Documentation](https://kustomize.io/)
