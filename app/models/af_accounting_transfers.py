import uuid
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class AfAccountingTransfer(Base):
    __tablename__ = "af_accounting_transfers"
    __table_args__ = {"schema": "public"}

    transfer_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    queue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public.af_accounting_queue.queue_id"),
        nullable=False
    )
    source_project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public.af_external_projects.external_project_id"),
        nullable=False
    )
    transaction_type = Column(String(60), nullable=False)
    payload_json = Column(JSONB, nullable=False)
    transfer_status = Column(String(20), nullable=False, default="sent")
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    accounting_entry_id = Column(String, nullable=True)
    response_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=True, default=0)
    external_endpoint_id = Column(UUID(as_uuid=True), nullable=True)

    queue = relationship("AfAccountingQueue")
    project = relationship("AfExternalProject")