FROM python:3.11-slim

# Install system dependencies including aria2
RUN apt-get update && apt-get install -y \
    aria2 \
    curl \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for health check (Render)
EXPOSE 7860

CMD ["python", "bot.py"]
