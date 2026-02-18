FROM python:3.11-slim

# Prevent python buffering (important for logs)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir requests python-dotenv

# Debug: show files in container
RUN ls -la

# Run script
CMD ["python","godmode.py"]

