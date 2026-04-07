from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependences.auth import get_current_user
from app.schemas.checks import (
    ListChecksRequest,
    PaginatedChecksResponse,
    CheckTypeListResponse,
)
from app.services.checks_service import ChecksService

router = APIRouter(
    prefix="/integration/accounting-vouchers",
    tags=["Accounting Vouchers"]
)


@router.get(
    "/types",
    response_model=CheckTypeListResponse,
    summary="Listar tipos únicos de comprobante",
    description="""
Retorna la lista de tipos únicos de comprobante disponibles en el módulo de integraciones contables.

Este endpoint se utiliza para poblar dinámicamente el filtro de tipos en el frontend.
Los tipos se obtienen directamente desde los registros existentes, por lo que cuando aparezcan
nuevos tipos de comprobante en la base de datos, también estarán disponibles aquí.
    """,
    responses={
        200: {
            "description": "Tipos de comprobante obtenidos exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {"value": "nomina contable", "label": "NOMINA CONTABLE"},
                            {"value": "transacciones", "label": "TRANSACCIONES"}
                        ]
                    }
                }
            },
        },
        401: {
            "description": "Token inválido o expirado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "AUTH_INVALID_TOKEN",
                            "meta": {}
                        }
                    }
                }
            },
        },
        403: {
            "description": "El usuario no tiene permisos para consultar tipos de comprobante",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "AUTH_INSUFFICIENT_PERMISSIONS",
                            "meta": {}
                        }
                    }
                }
            },
        },
    },
)
def list_transaction_types(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Lista los tipos únicos de comprobante.

    Args:
        db: Sesión activa de base de datos.
        current_user: Usuario autenticado.

    Returns:
        CheckTypeListResponse:
            Lista de tipos disponibles para el filtro del módulo de comprobantes.

    Raises:
        HTTPException 401:
            Si el token es inválido o expiró.

        HTTPException 403:
            Si el usuario no tiene permisos para consultar comprobantes.
    """
    service = ChecksService()
    return service.list_transaction_types(db, current_user)


@router.get(
    "",
    response_model=PaginatedChecksResponse,
    summary="Listar comprobantes",
    description="""
Retorna el listado paginado de comprobantes generados por las integraciones contables.

Permite filtrar por:
- texto de búsqueda,
- estado,
- proyecto,
- tipo de comprobante,
- rango de fechas.

Los resultados se ordenan por fecha de emisión descendente.
    """,
    responses={
        200: {
            "description": "Comprobantes obtenidos exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": "251f571",
                                "transaction_type": "NOMINA CONTABLE",
                                "project_name": "SIGMA",
                                "project_code": "SIGMA",
                                "state": "Fallido",
                                "issued_at": "2026-03-27T10:30:00",
                                "amount": 2500000.0,
                                "issued_by": "Carlos Pérez"
                            },
                            {
                                "id": "ba194a8",
                                "transaction_type": "TRANSACCIONES",
                                "project_name": "DISRIEGO",
                                "project_code": "DISRIEGO",
                                "state": "Cancelado",
                                "issued_at": "2026-03-20T08:15:00",
                                "amount": 980000.0,
                                "issued_by": "Laura Gómez"
                            }
                        ],
                        "total": 2,
                        "page": 1,
                        "size": 5,
                        "total_pages": 1
                    }
                }
            },
        },
        400: {
            "description": "Parámetros de paginación inválidos",
            "content": {
                "application/json": {
                    "examples": {
                        "page_index_invalid": {
                            "summary": "Índice de página inválido",
                            "value": {
                                "detail": {
                                    "code": "PAGE_INDEX_INVALID",
                                    "meta": {}
                                }
                            }
                        },
                        "page_size_invalid": {
                            "summary": "Tamaño de página inválido",
                            "value": {
                                "detail": {
                                    "code": "PAGE_SIZE_INVALID",
                                    "meta": {}
                                }
                            }
                        }
                    }
                }
            },
        },
        401: {
            "description": "Token inválido o expirado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "AUTH_INVALID_TOKEN",
                            "meta": {}
                        }
                    }
                }
            },
        },
        403: {
            "description": "El usuario no tiene permisos para listar comprobantes",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "AUTH_INSUFFICIENT_PERMISSIONS",
                            "meta": {}
                        }
                    }
                }
            },
        },
    },
)
def list_checks(
    db: Session = Depends(get_db),
    payload: ListChecksRequest = Depends(),
    current_user=Depends(get_current_user),
):
    """
    Lista los comprobantes de integración con filtros y paginación.

    Args:
        db: Sesión activa de base de datos.
        payload: Parámetros de consulta, filtros y paginación.
        current_user: Usuario autenticado.

    Returns:
        PaginatedChecksResponse:
            Respuesta paginada con los comprobantes encontrados.

    Raises:
        HTTPException 400:
            Si page_index o page_size son inválidos.

        HTTPException 401:
            Si el token es inválido o expiró.

        HTTPException 403:
            Si el usuario no tiene permisos para consultar comprobantes.
    """
    service = ChecksService()
    return service.list_checks(db, payload, current_user)