FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi==0.118.0 uvicorn[standard]==0.37.0

# Copy application files
COPY listener.py .
COPY start-listener.sh .

# Make the start script executable
RUN chmod +x start-listener.sh

# Expose port
EXPOSE 8000

# Run the start script
CMD ["./start-listener.sh"]
