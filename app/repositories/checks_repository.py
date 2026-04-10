from sqlalchemy.orm import Session
from sqlalchemy import cast, String, Numeric, or_, func

from app.models.af_accounting_transfers import AfAccountingTransfer
from app.models.af_accounting_queue import AfAccountingQueue
from app.models.af_external_projects import AfExternalProject
from app.models.users import Users


class ChecksRepository:
    def get_list_checks(self, db: Session, payload):
        """
        Consulta el listado de comprobantes con filtros dinámicos y paginación.

        Args:
            db: Sesión activa de base de datos.
            payload: Filtros de búsqueda, estado, proyecto, tipo y fechas.

        Returns:
            tuple:
                - rows: registros encontrados
                - total: cantidad total de registros
        """
        query = (
            db.query(
                AfAccountingTransfer.transfer_id.label("id"),
                AfAccountingTransfer.transaction_type.label("transaction_type"),
                AfExternalProject.project_name.label("project_name"),
                AfExternalProject.instance_code.label("project_code"),
                AfAccountingTransfer.transfer_status.label("state"),
                AfAccountingQueue.created_at.label("issued_at"),
                cast(
                    AfAccountingTransfer.payload_json["total"].astext,
                    Numeric
                ).label("amount"),
                Users.name.label("issued_by"),
            )
            .join(
                AfAccountingQueue,
                AfAccountingQueue.queue_id == AfAccountingTransfer.queue_id
            )
            .join(
                AfExternalProject,
                AfExternalProject.external_project_id == AfAccountingTransfer.source_project_id
            )
            .join(
                Users,
                Users.user_id == AfAccountingQueue.user_id
            )
        )

        if payload.search:
            search = f"%{payload.search.strip()}%"
            query = query.filter(
                or_(
                    cast(AfAccountingTransfer.transfer_id, String).ilike(search),
                    AfExternalProject.project_name.ilike(search),
                    AfExternalProject.instance_code.ilike(search),
                    Users.name.ilike(search),
                )
            )

        if payload.state:
            query = query.filter(
                func.lower(AfAccountingTransfer.transfer_status) == payload.state.lower()
            )

        if payload.project_id:
            query = query.filter(
                cast(AfAccountingTransfer.source_project_id, String) == payload.project_id
            )

        if payload.start_date:
            query = query.filter(AfAccountingQueue.created_at >= payload.start_date)

        if payload.end_date:
            query = query.filter(AfAccountingQueue.created_at <= payload.end_date)

        if payload.transaction_type:
            query = query.filter(
                func.lower(func.trim(AfAccountingTransfer.transaction_type))
                == payload.transaction_type.strip().lower()
            )

        total = query.count()
        offset = (payload.page_index - 1) * payload.page_size

        rows = (
            query
            .order_by(AfAccountingQueue.created_at.desc())
            .offset(offset)
            .limit(payload.page_size)
            .all()
        )

        return rows, total
    
    def get_transaction_types(self, db: Session):
        """
        Consulta los tipos únicos de comprobante existentes en la base de datos.

        Args:
            db: Sesión activa de base de datos.

        Returns:
            list:
                Lista de filas con value y label para poblar el select del frontend.
        """
        normalized_type = func.lower(func.trim(AfAccountingTransfer.transaction_type))

        rows = (
            db.query(
                normalized_type.label("value"),
                func.min(func.trim(AfAccountingTransfer.transaction_type)).label("label"),
            )
            .filter(AfAccountingTransfer.transaction_type.isnot(None))
            .filter(func.trim(AfAccountingTransfer.transaction_type) != "")
            .group_by(normalized_type)
            .order_by(normalized_type.asc())
            .all()
        )

        return rows