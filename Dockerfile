# ---Stage 1: Build Environment(Builder)---

# Pull official base image
FROM python:3.12-slim-bookworm AS builder

# Set work directory
WORKDIR /app

# Set environment variables 
# Prevent Python from writing pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1 

# Upgrade pip and install dependencies
RUN pip install --upgrade pip

# Copy the requirements file first
COPY ./requirements.txt .

# Install Python dependecies
RUN pip install --no-cache-dir -r requirements.txt

# ---Stage 2: Runtime environment(Production)---

# Pull official base image
FROM python:3.12-slim-bookworm

# Create the app user
RUN useradd -m -r appuser && \
    mkdir /app && \
    chown -R appuser /app

# Copy the Python dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Set the working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables to optimize Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Start the application
CMD [ "./entrypoint.sh"]