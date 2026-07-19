#!/bin/sh

# Ensure Python flushes logs instantly so you can see them in Railway
export PYTHONUNBUFFERED=1

# Run the backend API start command with explicitly enabled log capture
echo "Starting backend application!"
exec uvicorn src.api:app --host :: --port ${RAILWAY_API_PORT:-${PORT:-3000}} --log-level debg --workers 1