FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir mlflow==3.4.0 scikit-learn==1.7.2 pandas==2.3.3

# Copy the init script
COPY model-create.py .

# Make it executable
RUN chmod +x model-create.py

# Run the model-create script
CMD ["python", "model-create.py"]
