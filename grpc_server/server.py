import os
import time
import grpc
from concurrent import futures
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

import node_registry_pb2 as pb2
import node_registry_pb2_grpc as pb2_grpc

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Node(Base):
    __tablename__ = "nodes"
    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, unique=True, nullable=False, index=True)
    host       = Column(String, nullable=False)
    port       = Column(Integer, nullable=False)
    status     = Column(String, default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)


def _to_proto(node: Node) -> pb2.NodeResponse:
    return pb2.NodeResponse(
        id=node.id,
        name=node.name,
        host=node.host,
        port=node.port,
        status=node.status,
        created_at=node.created_at.isoformat(),
        updated_at=node.updated_at.isoformat(),
    )


class NodeRegistryServicer(pb2_grpc.NodeRegistryServicer):

    def Register(self, request, context):
        db = SessionLocal()
        try:
            existing = db.query(Node).filter(Node.name == request.name).first()
            if existing:
                context.set_code(grpc.StatusCode.ALREADY_EXISTS)
                context.set_details("Node already exists")
                return pb2.NodeResponse()
            node = Node(name=request.name, host=request.host, port=request.port)
            db.add(node)
            db.commit()
            db.refresh(node)
            return _to_proto(node)
        finally:
            db.close()

    def List(self, request, context):
        db = SessionLocal()
        try:
            nodes = db.query(Node).all()
            return pb2.NodeList(nodes=[_to_proto(n) for n in nodes])
        finally:
            db.close()

    def Get(self, request, context):
        db = SessionLocal()
        try:
            node = db.query(Node).filter(Node.name == request.name).first()
            if not node:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Node not found")
                return pb2.NodeResponse()
            return _to_proto(node)
        finally:
            db.close()

    def Delete(self, request, context):
        db = SessionLocal()
        try:
            node = db.query(Node).filter(Node.name == request.name).first()
            if not node:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Node not found")
                return pb2.Empty()
            node.status = "inactive"
            node.updated_at = datetime.now(timezone.utc)
            db.commit()
            return pb2.Empty()
        finally:
            db.close()


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_NodeRegistryServicer_to_server(NodeRegistryServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC server listening on port 50051", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    time.sleep(2)
    serve()