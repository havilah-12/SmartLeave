FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY uv.lock .
COPY .env .
COPY config/ ./config/
COPY src/ ./src/

# Install dependencies using uv
RUN uv sync --no-dev

# Initialize the database with mock data
RUN python src/database/init_db.py

# Expose port for ADK API server
EXPOSE 8080

# Run the agent API server
CMD ["uv", "run", "adk", "api_server", "src/multi_agent/leaves_agent_parallel", "--host", "0.0.0.0", "--port", "8080"]
