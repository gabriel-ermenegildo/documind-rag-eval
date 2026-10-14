import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from documind.db.models import EMBEDDING_DIMENSION, Chunk, Document

pytestmark = pytest.mark.integration

APPLICATION_TABLES = {"documents", "chunks", "query_logs"}


def make_document() -> Document:
    return Document(filename="lei.pdf", sha256="a" * 64, status="ready")


def make_chunk(document: Document, content: str) -> Chunk:
    return Chunk(
        document_id=document.id,
        chunking_strategy="fixed_512_64",
        chunk_index=0,
        content=content,
        page_start=1,
        page_end=1,
        char_start=0,
        char_end=len(content),
    )


@pytest.fixture
def session(db_engine):
    """Session whose changes are rolled back, so each test starts from empty tables."""
    with Session(db_engine) as session:
        yield session
        session.rollback()


def test_upgrade_creates_tables_indexes_and_extension(db_engine):
    inspector = inspect(db_engine)

    assert set(inspector.get_table_names()) >= APPLICATION_TABLES
    # Superset, not equality: Postgres also lists the index that backs the unique constraint.
    assert {index["name"] for index in inspector.get_indexes("chunks")} >= {
        "chunks_embedding_hnsw",
        "chunks_tsv_gin",
        "chunks_strategy_idx",
    }
    assert [
        constraint["column_names"] for constraint in inspector.get_unique_constraints("chunks")
    ] == [["document_id", "chunking_strategy", "chunk_index"]]
    with db_engine.connect() as connection:
        assert connection.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")) == 1


def test_models_match_the_migrated_schema(db_engine, alembic_config):
    # Raises if autogenerate would produce any change, i.e. models and migrations drifted apart.
    command.check(alembic_config)


def test_chunk_round_trip_uses_database_generated_columns(session):
    document = make_document()
    session.add(document)
    session.flush()
    chunk = make_chunk(document, "Os prazos foram prorrogados")
    chunk.embedding = [0.5] * EMBEDDING_DIMENSION
    session.add(chunk)
    session.flush()
    session.expire_all()

    stored = session.scalars(select(Chunk)).one()

    # Portuguese stemming and stop words: "os" and "foram" are dropped, the rest is stemmed.
    assert stored.tsv == "'praz':2 'prorrog':4"
    assert stored.metadata_ == {}
    assert list(stored.embedding) == [0.5] * EMBEDDING_DIMENSION
    assert stored.document_id == document.id


def test_deleting_a_document_deletes_its_chunks(session):
    document = make_document()
    session.add(document)
    session.flush()
    session.add(make_chunk(document, "texto"))
    session.flush()

    session.execute(text("DELETE FROM documents WHERE id = :id"), {"id": document.id})

    assert session.scalars(select(Chunk)).all() == []


def test_downgrade_removes_everything_and_upgrade_restores_it(db_engine, alembic_config):
    command.downgrade(alembic_config, "base")
    try:
        inspector = inspect(db_engine)
        assert APPLICATION_TABLES.isdisjoint(inspector.get_table_names())
        with db_engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                is None
            )
    finally:
        command.upgrade(alembic_config, "head")

    assert set(inspect(db_engine).get_table_names()) >= APPLICATION_TABLES
