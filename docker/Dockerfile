ARG MLFLOW_VERSION

FROM ghcr.io/mlflow/mlflow:v${MLFLOW_VERSION}

COPY requirements.txt .
RUN pip install -r requirements.txt && \
    rm requirements.txt
