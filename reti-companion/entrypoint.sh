#!/bin/bash

echo "Starting Data Collector Container..."
echo "Django API URL: $DJANGO_API_BASE_URL"

# Wait for Django to be ready
echo "Waiting for Django API to be ready..."
while ! curl -f "$DJANGO_API_BASE_URL/health/" 2>/dev/null; do
    echo "Waiting for Django API..."
    sleep 5
done

echo "Django API is ready!"

# Start cron daemon
echo "Starting cron daemon..."
service cron start

# Run initial collection
echo "Running initial data collection..."
python /app/scripts/data_collector.py -c update
python /app/scripts/release_old_ips.py --days 30
python /app/scripts/network_cleanup.py

# Keep container running
echo "Data collector is ready. Monitoring for scheduled runs..."
tail -f /var/log/data-collector/collector.log 
