FROM python:3.14-slim AS builder
WORKDIR /app
COPY grpc_server/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.14-slim
WORKDIR /app
COPY --from=builder /install /usr/local
RUN useradd -m appuser

COPY proto/node_registry.proto proto/node_registry.proto
RUN python -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/node_registry.proto

USER appuser
COPY grpc_server/server.py .
EXPOSE 50051
CMD ["python", "server.py"]