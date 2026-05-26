import os
import grpc
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from typing import Optional

import node_registry_pb2 as pb2
import node_registry_pb2_grpc as pb2_grpc
import time

GRPC_HOST = os.environ.get("GRPC_HOST", "grpc-server")
GRPC_PORT = os.environ.get("GRPC_PORT", "50051")

app = FastAPI()

def get_stub():
    address = f"{GRPC_HOST}:{GRPC_PORT}"
    for attempt in range(10):
        try:
            channel = grpc.insecure_channel(address)
            grpc.channel_ready_future(channel).result(timeout=3)
            return pb2_grpc.NodeRegistryStub(channel)
        except grpc.FutureTimeoutError:
            time.sleep(2)
    raise RuntimeError(f"Cannot connect to gRPC server at {address}")

class NodeCreate(BaseModel):
    name: str
    host: str
    port: int = Field(gt=0, le=65535)


class NodeUpdate(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = Field(default=None, gt=0, le=65535)


def _node_to_dict(n):
    return {
        "id": n.id, "name": n.name, "host": n.host, "port": n.port,
        "status": n.status, "created_at": n.created_at, "updated_at": n.updated_at,
    }


@app.get("/health")
def health():
    try:
        stub = get_stub()
        stub.List(pb2.Empty(), timeout=2)
        grpc_status = "connected"
    except Exception:
        grpc_status = "disconnected"
    return {"status": "ok", "grpc": grpc_status}


@app.post("/api/nodes", status_code=201)
def register_node(node: NodeCreate):
    stub = get_stub()
    try:
        resp = stub.Register(
            pb2.RegisterRequest(name=node.name, host=node.host, port=node.port)
        )
        return _node_to_dict(resp)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail="Node already exists")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/nodes")
def list_nodes():
    stub = get_stub()
    try:
        resp = stub.List(pb2.Empty())
        return [_node_to_dict(n) for n in resp.nodes]
    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/nodes/{name}")
def get_node(name: str):
    stub = get_stub()
    try:
        resp = stub.Get(pb2.GetRequest(name=name))
        return _node_to_dict(resp)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Node not found")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/nodes/{name}", status_code=204)
def delete_node(name: str):
    stub = get_stub()
    try:
        stub.Delete(pb2.DeleteRequest(name=name))
        return Response(status_code=204)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Node not found")
        raise HTTPException(status_code=500, detail=str(e))