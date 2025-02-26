FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY arrranger_sync.py .
COPY arrranger_scheduler.py .
COPY arrranger_instances.json.example .
COPY entrypoint.sh .

# Create config and data directories
RUN mkdir -p /config /data

# Set environment variables
ENV CONFIG_DIR=/config
ENV DATA_DIR=/data
ENV CONFIG_FILE=/config/arrranger_instances.json
ENV DB_NAME=/data/arrranger.db

# Create non-root user
RUN useradd -u 1000 -M -s /bin/bash arrranger && \
    touch /data/arrranger.db && \
    chmod -R 755 /app /config /data && \
    chmod 666 /data/arrranger.db && \
    chown -R arrranger:arrranger /app /config /data /data/arrranger.db && \
    chmod +x /app/entrypoint.sh

# Switch to non-root user
USER arrranger

# Command to run the application
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "arrranger_scheduler.py"]
