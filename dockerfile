# ==============================================================================
# Stage 1: The Builder (This stage remains unchanged)
# ==============================================================================
FROM python:3.9-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    gdk-pixbuf2.0 \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Stage 2: The Final Image (This stage is modified)
# ==============================================================================
FROM python:3.9-slim

WORKDIR /app

# Prevent python from writing .pyc files and disable buffering
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# --- MODIFICATION IS HERE ---
# Install RUNTIME system dependencies for WeasyPrint AND wkhtmltopdf
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    gdk-pixbuf2.0 \
    wkhtmltopdf \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*
# --- END OF MODIFICATION ---

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Set the PATH to include the virtual environment's binaries
ENV PATH="/opt/venv/bin:$PATH"

# ... (the rest of the Dockerfile remains the same)
RUN addgroup --system app && adduser --system --group app
COPY . .
RUN chown -R app:app /app
USER app

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "run:app"]