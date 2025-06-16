FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libsnmp-dev \
    libsmi2-dev \
    libssl-dev \
    curl \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create log directory
RUN mkdir -p /var/log/data-collector

# Create crontab for scheduled collection
COPY crontab /etc/cron.d/data-collector

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/data-collector

# Apply cron job
RUN crontab /etc/cron.d/data-collector

# Create entrypoint script
RUN echo '#!/bin/bash\n\
echo "Starting Data Collector..."\n\
\n\
# Wait for Django API to be available\n\
echo "Waiting for Django API at $DJANGO_API_BASE_URL/health/"\n\
while ! curl -f "$DJANGO_API_BASE_URL/health/" >/dev/null 2>&1; do\n\
    echo "Django API is not ready yet, waiting..."\n\
    sleep 5\n\
done\n\
echo "Django API is ready!"\n\
\n\
# Start cron daemon\n\
echo "Starting cron daemon..."\n\
cron\n\
\n\
# Start web dashboard in background\n\
echo "Starting web dashboard on port 8001..."\n\
cd /app && python scripts/web_dashboard.py &\n\
\n\
# Run initial collection\n\
echo "Running initial data collection..."\n\
cd /app && python scripts/data_collector.py -c update\n\
\n\
# Keep container running and show logs\n\
echo "Data collector started. Monitoring logs..."\n\
tail -f /var/log/data-collector/*.log\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose port for web dashboard
EXPOSE 8001

# Run entrypoint
CMD ["/app/entrypoint.sh"] 