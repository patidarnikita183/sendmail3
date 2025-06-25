#!/bin/bash

set -e

echo "🚀 Starting Email Tracking App Deployment..."

# Check Docker installation
if ! command -v docker &> /dev/null
then
    echo "[ERROR] Docker is not installed. Please install Docker Desktop first."
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null
then
    echo "[ERROR] Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "[INFO] Building Docker image..."
docker build -t email-tracking-app .

echo "[INFO] Stopping and removing any existing container..."
docker rm -f email-tracker 2>/dev/null || true

echo "[INFO] Running Docker container..."
docker run -d \
  -p 9000:9000 \
  --name email-tracker \
  email-tracking-app

echo "[INFO] Deployment successful. App is live at http://localhost:9000/"
