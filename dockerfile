# ==============================================================================
# Stage 1: The Builder (No changes)
# ==============================================================================
FROM python:3.9-slim as builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Stage 2: The Final Image (Corrected Order)
# ==============================================================================
FROM python:3.9-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    gdk-pixbuf2.0 \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# --- MODIFICATION IS HERE: PERFORM ALL ROOT OPERATIONS FIRST ---
# 1. Create the user and group first.
RUN addgroup --system app && adduser --system --group app

# 2. Copy the application code. This is still owned by root.
COPY . .

# 3. Make the entrypoint script executable WHILE STILL ROOT.
RUN chmod +x entrypoint.sh

# 4. Now, change the ownership of EVERYTHING to the 'app' user.
RUN chown -R app:app /app

# 5. Finally, switch to the non-root user for runtime.
USER app
# --- END OF MODIFICATION ---

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "run:app"]