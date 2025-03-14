# Use Python 3.11 as base image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libogg-dev \
    libvorbis-dev \
    libopus-dev \
    git \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies only for the server
RUN pip install grpcio protobuf pyaudio "pyogg @ git+https://github.com/TeamPyOgg/PyOgg@4118fc4"

# Copy server code
COPY . .

# Expose gRPC port
EXPOSE 50051

# Run server
CMD ["python", "server.py"]