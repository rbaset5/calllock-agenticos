FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends gcc curl && rm -rf /var/lib/apt/lists/*

# Install Python deps (from harness/)
COPY harness/requirements.txt harness/pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy harness source
COPY harness/src/ ./src/

# Copy knowledge files (needed by extraction pipeline)
COPY knowledge/ /knowledge/

# Set Python path so imports work
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "harness.server:app", "--host", "0.0.0.0", "--port", "8000"]
