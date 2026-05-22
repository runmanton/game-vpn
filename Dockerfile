# GameVPN Signaling Server - Docker
# Deploy free on Render, Railway, or Fly.io
FROM python:3.11-slim

WORKDIR /app
COPY server/ ./server/
COPY run_server.py .

RUN pip install --no-cache-dir fastapi uvicorn[standard] websockets

EXPOSE 8765

CMD ["python", "run_server.py"]
