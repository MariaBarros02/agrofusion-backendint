import uuid
from sqlalchemy import Column, String, Date, DateTime, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class AfAccountingQueue(Base):
    __tablename__ = "af_accounting_queue"
    __table_args__ = {"schema": "public"}

    queue_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public.af_external_projects.external_project_id"),
        nullable=False
    )
    source_module_code = Column(String(60), nullable=False)
    transaction_type = Column(String(60), nullable=False)
    transaction_data = Column(JSONB, nullable=False)
    accounting_date = Column(Date, nullable=False)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public.users.user_id"),
        nullable=False
    )
    status = Column(String(20), nullable=False, default="pending")
    priority = Column(Integer, nullable=False, default=5)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    external_transaction_id = Column(UUID(as_uuid=True), nullable=True)

    project = relationship("AfExternalProject")
    user = relationship("Users")