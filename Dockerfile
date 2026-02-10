FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for Reflex)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create certs directory
RUN mkdir -p /app/certs

# Initialize Reflex
RUN reflex init

# Expose ports
EXPOSE 3000 8000

# Run the application
CMD ["reflex", "run", "--env", "prod", "--backend-host", "0.0.0.0"]
