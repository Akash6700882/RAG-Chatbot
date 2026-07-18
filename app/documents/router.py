"""Document ingestion endpoints: upload, list, delete."""

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.exceptions import NotFoundError, UnsupportedFileTypeError
from app.core.logging import get_logger
from app.db.models import Document, User
from app.db.session import get_db
from app.documents.schemas import DocumentResponse
from app.ingestion.loaders import SUPPORTED_EXTENSIONS
from app.ingestion.pipeline import ingest_file
from app.vectorstore.factory import get_vector_store

router = APIRouter(tags=["documents"])
logger = get_logger(__name__)


@router.post("/upload", response_model=DocumentResponse, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}'. Supported types: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    document = Document(
        owner_id=current_user.id,
        filename=file.filename or "unnamed",
        file_type=suffix.lstrip("."),
        status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest_path = upload_dir / f"{document.id}{suffix}"

    try:
        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        chunk_count = ingest_file(
            str(dest_path),
            document_id=document.id,
            filename=document.filename,
            owner_id=current_user.id,
        )
        document.status = "ready"
        document.chunk_count = chunk_count
    except Exception:
        document.status = "failed"
        logger.exception("Ingestion failed for document %s", document.id)
        raise
    finally:
        db.commit()
        db.refresh(document)

    return document


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.owner_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    document = db.get(Document, document_id)
    if document is None or document.owner_id != current_user.id:
        raise NotFoundError("Document not found")

    get_vector_store().delete(document_id)

    settings = get_settings()
    file_path = Path(settings.upload_dir) / f"{document_id}.{document.file_type}"
    if file_path.exists():
        file_path.unlink()

    db.delete(document)
    db.commit()
