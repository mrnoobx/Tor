FROM node:18-slim

# Install webtorrent CLI
RUN npm install -g webtorrent-cli

# Create working dir
WORKDIR /app

# Copy source
COPY . .

# Install dependencies
RUN npm install

# Expose port
EXPOSE 3000

# Run bot
CMD ["node", "index.js"]
