# Use Python 3.13 slim image
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Set working directory
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY .env .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Default command to run the MCP server
CMD ["uv", "run", "src/retail_chain_mcp.py"]