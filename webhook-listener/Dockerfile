# Multi-stage build using pixi for reproducible dependencies
FROM ghcr.io/prefix-dev/pixi:latest AS builder

WORKDIR /build

# Copy pixi project files
COPY pixi.toml pixi.lock ./

# Copy source code for package installation
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies from lock file (production environment only, no dev dependencies)
RUN pixi install --locked --environment default

# Final stage - use a slim Python image
FROM python:3.11-slim

WORKDIR /app

# Copy the pixi environment from builder
COPY --from=builder /build/.pixi/envs/default /opt/conda

# Copy source code and templates
COPY src/ /app/src/
COPY templates/ /app/templates/

# Add conda environment to PATH
ENV PATH=/opt/conda/bin:$PATH

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "src.main"]
