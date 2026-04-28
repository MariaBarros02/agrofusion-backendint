import math

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import int_error
from app.repositories.checks_repository import ChecksRepository
from app.schemas.checks import (
    ListChecksRequest,
    CheckDetailResponse,
    CheckListItemResponse,
    PaginatedChecksResponse,
    CheckTypeOptionResponse,
    CheckTypeListResponse,
)
from app.services.permissions_service import PermissionsService


class ChecksService:
    def __init__(self):
        self.repo = ChecksRepository()
        self.perm_service = PermissionsService()

    def get_check_detail(
        self,
        db: Session,
        check_id: str,
        current_user: dict
    ):
        """
        Retorna el detalle de un comprobante contable.
        """
        if not self.perm_service.validate_permission(
            db,
            current_user.get("role"),
            "043"
        ):
            int_error("AUTH_INSUFFICIENT_PERMISSIONS", status.HTTP_403_FORBIDDEN)

        row = self.repo.get_check_detail(db, check_id)
        if not row:
            int_error("CHECK_NOT_FOUND", status.HTTP_404_NOT_FOUND)

        return CheckDetailResponse(
            id=str(row.id),
            queue_id=str(row.queue_id),
            source_project_id=str(row.source_project_id),
            transaction_type=row.transaction_type,
            project_name=row.project_name,
            project_code=row.project_code,
            state=row.state,
            issued_at=row.issued_at,
            amount=float(row.amount) if row.amount is not None else None,
            issued_by=row.issued_by,
            source_module_code=row.source_module_code,
            accounting_date=row.accounting_date,
            sent_at=row.sent_at,
            acknowledged_at=row.acknowledged_at,
            accounting_entry_id=(
                str(row.accounting_entry_id) if row.accounting_entry_id else None
            ),
            response_json=row.response_json,
            payload_json=row.payload_json,
            transaction_data=row.transaction_data,
            error_message=row.error_message,
            retry_count=row.retry_count,
            queue_status=row.queue_status,
            attempts=row.attempts,
            max_attempts=row.max_attempts,
            last_error=row.last_error,
        )

    def list_checks(

        self,
        db: Session,
        payload: ListChecksRequest,
        current_user: dict
    ):

        """
        Lista los comprobantes de integración con filtros y paginación.

        Args:
            db: Sesión activa de base de datos.
            payload: Filtros de búsqueda y parámetros de paginación.
            current_user: Usuario autenticado.

        Returns:
            PaginatedChecksResponse:
                Respuesta paginada con los comprobantes encontrados.

        Raises:
            HTTPException 403:
                Si el usuario no tiene permisos.
            HTTPException 400:
                Si los parámetros de paginación son inválidos.
        """

        # Validar permisos
        if not self.perm_service.validate_permission(
            db,
            current_user.get("role"),
            "034"
        ):
            int_error("AUTH_INSUFFICIENT_PERMISSIONS", status.HTTP_403_FORBIDDEN)

        # Validaciones de paginación
        if payload.page_index < 1:
            int_error("PAGE_INDEX_INVALID", status.HTTP_400_BAD_REQUEST)

        if payload.page_size < 1:
            int_error("PAGE_SIZE_INVALID", status.HTTP_400_BAD_REQUEST)

        # Obtener datos
        rows, total = self.repo.get_list_checks(db, payload)

        # Calcular total de páginas
        total_pages = math.ceil(total / payload.page_size) if total else 1

        # Mapear resultados
        items = [
            CheckListItemResponse(
                id=str(row.id),
                transaction_type=row.transaction_type,
                project_name=row.project_name,
                project_code=row.project_code,
                state=row.state,
                issued_at=row.issued_at,
                amount=float(row.amount) if row.amount is not None else None,
                issued_by=row.issued_by,
            )
            for row in rows
        ]

        # Respuesta final
        return PaginatedChecksResponse(
            items=items,
            total=total,
            page=payload.page_index,
            size=payload.page_size,
            total_pages=total_pages,
        )

    def list_transaction_types(self, db: Session, current_user: dict):
        """
        Obtiene los tipos únicos de comprobante disponibles.

        Args:
            db: Sesión activa de base de datos.
            current_user: Usuario autenticado.

        Returns:
            CheckTypeListResponse:
                Lista de tipos únicos normalizados para el filtro del frontend.

        Raises:
            HTTPException 403:
                Si el usuario no tiene permisos para consultar comprobantes.
        """
        if not self.perm_service.validate_permission(
            db,
            current_user.get("role"),
            "034"
        ):
            int_error("AUTH_INSUFFICIENT_PERMISSIONS", status.HTTP_403_FORBIDDEN)

        rows = self.repo.get_transaction_types(db)

        return CheckTypeListResponse(
            items=[
                CheckTypeOptionResponse(
                    value=row.value,
                    label=row.label,
                )
                for row in rows
            ]
        )
