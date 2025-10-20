.PHONY: build push build-push login help

# Docker image configuration
IMAGE_REGISTRY := quay.io
IMAGE_ORG := openteams
IMAGE_NAME := mlflow-webhook-listener
IMAGE_TAG := latest
IMAGE_FULL := $(IMAGE_REGISTRY)/$(IMAGE_ORG)/$(IMAGE_NAME):$(IMAGE_TAG)

help:
	@echo "Available targets:"
	@echo "  build       - Build the Docker image"
	@echo "  push        - Push the Docker image to registry"
	@echo "  build-push  - Build and push in one command"
	@echo "  login       - Login to quay.io registry"
	@echo ""
	@echo "Image: $(IMAGE_FULL)"

login:
	@echo "Logging in to $(IMAGE_REGISTRY)..."
	docker login $(IMAGE_REGISTRY)

build:
	@echo "Building Docker image: $(IMAGE_FULL)"
	docker build -t $(IMAGE_FULL) .
	@echo "Build complete!"

push:
	@echo "Pushing Docker image: $(IMAGE_FULL)"
	docker push $(IMAGE_FULL)
	@echo "Push complete!"

build-push: build push
	@echo "Build and push complete!"
