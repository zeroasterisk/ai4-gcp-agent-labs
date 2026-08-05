FROM python:3.13-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tools.py server.py ./

ENV PORT=8080
EXPOSE 8080
# Cloud Run injects $PORT; uvicorn serves the Streamable HTTP MCP app at /mcp.
CMD exec uvicorn server:app --host 0.0.0.0 --port ${PORT}
