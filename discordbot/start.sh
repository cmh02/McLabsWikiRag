#!/bin/sh

# Ensure Python flushes logs instantly so you can see them in Railway
export PYTHONUNBUFFERED=1

# Run the discord bot start command with explicitly enabled log capture
echo "Starting discord bot application!"
exec uvicorn discordbot.bot:app --host :: --port ${RAILWAY_DISCORD_PORT:-${PORT:-3000}} --log-level debug --workers 1
