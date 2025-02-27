FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including timezone support and gosu
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tzdata \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY arrranger_sync.py .
COPY arrranger_scheduler.py .
COPY arrranger_instances.json.example .
COPY arrranger_logging.py .
COPY entrypoint.sh .

# Create config and data directories
RUN mkdir -p /config /data

# Set environment variables
ENV CONFIG_DIR=/config
ENV DATA_DIR=/data
ENV CONFIG_FILE=/config/arrranger_instances.json
ENV DB_NAME=/data/arrranger.db

# Make entrypoint executable and set proper permissions
RUN chmod +x /app/entrypoint.sh && \
    chmod -R 755 /app /config /data && \
    touch /data/arrranger.db && \
    chmod 666 /data/arrranger.db

# Run as root to allow entrypoint.sh to switch users
USER root

# Command to run the application
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "arrranger_scheduler.py"]
