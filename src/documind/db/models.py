"""SQLAlchemy models. They mirror the schema in docs/ARCHITECTURE.md, section 4."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Fixed by the column type: changing the embedding model's dimension needs a migration.
EMBEDDING_DIMENSION = 768

# Deterministic constraint names, so later migrations can refer to them.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Python str maps to TEXT (not VARCHAR) and dict to JSONB unless a column says otherwise.
    type_annotation_map = {str: Text, dict[str, Any]: JSONB}


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str]
    sha256: Mapped[str] = mapped_column(CHAR(64), unique=True)
    title: Mapped[str | None]
    num_pages: Mapped[int | None]
    status: Mapped[str]
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunking_strategy",
            "chunk_index",
            name="uq_chunks_document_strategy_index",
        ),
        Index(
            "chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("chunks_tsv_gin", "tsv", postgresql_using="gin"),
        Index("chunks_strategy_idx", "chunking_strategy"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunking_strategy: Mapped[str]
    chunk_index: Mapped[int]
    content: Mapped[str]
    page_start: Mapped[int]
    page_end: Mapped[int]
    # Offsets into the full concatenated text of the document.
    char_start: Mapped[int]
    char_end: Mapped[int]
    token_count: Mapped[int | None]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION))
    # Maintained by Postgres from `content`; never written by the application.
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('portuguese', content)", persisted=True)
    )
    # `metadata` is reserved by the declarative base, hence the trailing underscore.
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", server_default=text("'{}'"))


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question: Mapped[str]
    config: Mapped[dict[str, Any]]
    retrieved_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
    answer: Mapped[dict[str, Any] | None]
    latency_ms: Mapped[dict[str, Any]]
    tokens: Mapped[dict[str, Any] | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
