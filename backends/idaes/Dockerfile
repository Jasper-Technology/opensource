FROM python:3.11-slim

# Install system dependencies for IPOPT and cyipopt
RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    liblapack-dev \
    libblas-dev \
    pkg-config \
    wget \
    curl \
    coinor-libipopt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install cyipopt (Python binding for system IPOPT)
RUN pip install --no-cache-dir cyipopt

# Create non-root user WITH home directory (IDAES needs ~/.idaes/)
RUN useradd --create-home --shell /bin/false appuser

# Install IDAES extensions as root, then copy to appuser's home
RUN idaes get-extensions --distro ubuntu2204 --verbose || true
RUN cp -r /root/.idaes /home/appuser/.idaes 2>/dev/null || true && \
    chown -R appuser:appuser /home/appuser/.idaes 2>/dev/null || true

# Also put IPOPT on the system PATH for Pyomo's SolverFactory
RUN cp /root/.idaes/bin/ipopt /usr/local/bin/ipopt 2>/dev/null || true && \
    chmod +x /usr/local/bin/ipopt 2>/dev/null || true

# Copy application code
COPY app/ ./app/

USER appuser

# Railway sets PORT environment variable
ENV PORT=8000
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:$PORT/api/health || exit 1

# Run server
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
