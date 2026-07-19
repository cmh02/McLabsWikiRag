# Use a lightweight python image
FROM python:3.11-slim

# Force Python to flush all print/logging statements instantly to the console
ENV PYTHONUNBUFFERED=1

# Ensure we don't get stuck on interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*


# Set the working directory for the Python app
WORKDIR /app

# Copy the requirements file and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files into /app
COPY . .

# Explicitly pull start.sh out to the container root for bulletproof execution
# (Adjust "discordbot/start.sh" if your script is located elsewhere in your repo)
COPY discordbot/start.sh /start.sh
RUN chmod +x /start.sh

# Expose the application port
EXPOSE 3000

# Set entrypoint to the startup script at the root level
CMD ["/start.sh"]
