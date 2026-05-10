from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependences.auth import get_current_user
from app.schemas.checks import (
    CheckDetailResponse,
    ListChecksRequest,
    PaginatedChecksResponse,
    CheckTypeListResponse,
    AccountingConsultRequest,
    AccountingConsultResponse,
    AccountingTransferRequest,
    AccountingTransferResponse,
    AccountingACKRequest,
    AccountingACKResponse,
    AccountingACKRequest
)
from app.services.checks_service import ChecksService


router = APIRouter(
    tags=["Accounting Vouchers"]
)

vouchers_router = APIRouter(
    prefix="/integration/accounting-vouchers",
    tags=["Accounting Vouchers"]
)


@vouchers_router.get(
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
    service = ChecksService()
    return service.list_transaction_types(db, current_user)


@router.get(
    "/{check_id}",
    response_model=CheckDetailResponse,
    summary="Detalle de comprobante",
    description="Retorna el detalle de un comprobante generado por integraciones contables.",
)
def get_check_detail(
    check_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ChecksService()
    return service.get_check_detail(db, check_id, current_user)


@vouchers_router.get(
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
    service = ChecksService()
    return service.list_checks(db, payload, current_user)



@vouchers_router.post(
    "/consult",
    response_model=AccountingConsultResponse,
    summary="Consultar información contable externa",
    description="""
Consulta la información contable externa de un proyecto para un periodo específico.

El endpoint recibe:
- identificador del proyecto externo,
- identificador del endpoint externo configurado,
- fecha inicial del periodo,
- fecha final del periodo.

Con esta información, el sistema consulta el endpoint externo configurado y retorna
la información contable normalizada con metadata, resumen, facturas y transacciones.
    """,
    responses={
        200: {
            "description": "Información contable obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "metadata": {
                            "ExchangeId": "AF-2026-04-000001",
                            "GeneratedAt": "2026-04-21T02:04:24.456911",
                            "StandardVersion": "1.0",
                            "RequestedPeriod": {
                                "From": "2025-04-01",
                                "To": "2025-04-30"
                            },
                            "SourceSystem": {
                                "SystemId": "disriego-prod-01",
                                "SystemName": "Disriego",
                                "SystemNIT": "901724254",
                                "Environment": "production"
                            },
                            "GeneratedBy": "disriego-api"
                        },
                        "summary": {
                            "TotalDocuments": 18,
                            "TotalInvoices": 12,
                            "TotalTransactions": 6,
                            "TotalGrossAmount": 2500000.0,
                            "TotalNet": 2300000.0,
                            "Currency": "COP"
                        },
                        "invoices": [],
                        "transactions": []
                    }
                }
            },
        },
        400: {
            "description": "Solicitud inválida o configuración incorrecta del endpoint externo",
            "content": {
                "application/json": {
                    "examples": {
                        "external_project_required": {
                            "summary": "Proyecto externo obligatorio",
                            "value": {
                                "detail": {
                                    "code": "EXTERNAL_PROJECT_ID_REQUIRED",
                                    "meta": {}
                                }
                            }
                        },
                        "external_endpoint_required": {
                            "summary": "Endpoint externo obligatorio",
                            "value": {
                                "detail": {
                                    "code": "EXTERNAL_ENDPOINT_ID_REQUIRED",
                                    "meta": {}
                                }
                            }
                        },
                        "since_period_required": {
                            "summary": "Fecha inicial obligatoria",
                            "value": {
                                "detail": {
                                    "code": "SINCE_PERIOD_REQUIRED",
                                    "meta": {}
                                }
                            }
                        },
                        "until_period_required": {
                            "summary": "Fecha final obligatoria",
                            "value": {
                                "detail": {
                                    "code": "UNTIL_PERIOD_REQUIRED",
                                    "meta": {}
                                }
                            }
                        },
                        "period_format_invalid": {
                            "summary": "Formato de periodo inválido",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_PERIOD_FORMAT_INVALID",
                                    "meta": {}
                                }
                            }
                        },
                        "period_range_invalid": {
                            "summary": "Rango de periodo inválido",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_PERIOD_RANGE_INVALID",
                                    "meta": {}
                                }
                            }
                        },
                        "endpoint_method_invalid": {
                            "summary": "Método del endpoint externo inválido",
                            "value": {
                                "detail": {
                                    "code": "EXTERNAL_ENDPOINT_METHOD_INVALID",
                                    "meta": {}
                                }
                            }
                        },
                        "endpoint_url_empty": {
                            "summary": "URL del endpoint externo vacía",
                            "value": {
                                "detail": {
                                    "code": "EXTERNAL_ENDPOINT_URL_EMPTY",
                                    "meta": {}
                                }
                            }
                        },
                        "endpoint_url_template_invalid": {
                            "summary": "Plantilla de URL inválida",
                            "value": {
                                "detail": {
                                    "code": "EXTERNAL_ENDPOINT_URL_TEMPLATE_INVALID",
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
            "description": "El usuario no tiene permisos para consultar información contable externa",
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
        404: {
            "description": "No se encontró la configuración del endpoint externo",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "EXTERNAL_ENDPOINT_NOT_FOUND",
                            "meta": {}
                        }
                    }
                }
            },
        },
        409: {
            "description": "Ya existe una transferencia contable para el periodo solicitado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "ACCOUNTING_TRANSFER_PERIOD_ALREADY_EXISTS",
                            "meta": {}
                        }
                    }
                }
            },
        },
        502: {
            "description": "Error consultando el endpoint externo",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "EXT_ACCOUNTING_INFO",
                            "meta": {}
                        }
                    }
                }
            },
        },
    },
)
def consult_accounting(
    request: Request,
    payload: AccountingConsultRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ChecksService()

    ip = request.headers.get("x-forwarded-for")

    if ip:
        ip = ip.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    else:
        ip = None

    user_agent = request.headers.get("user-agent")

    return service.consult_accounting(
        db=db,
        payload=payload,
        current_user=current_user,
        ip=ip,
        user_agent=user_agent,
    )


@router.post(
    "/accounting-transfer",
    response_model=AccountingTransferResponse,
    summary="Transferir lote contable a contabilidad",
    description="""
Envía a contabilidad el JSON normalizado previamente consultado desde el proyecto externo.

El endpoint:
- valida el permiso 043 - Transferir lotes contables,
- busca el endpoint de contabilidad configurado,
- toma el método HTTP desde cat_terms,
- toma la API key desde response_template,
- envía el JSON normalizado a contabilidad,
- registra el lote en af_accounting_transfers con estado processing,
- registra los documentos en af_audit_receipts,
- registra auditoría de la operación.
    """,
    responses={
        200: {
            "description": "Lote contable enviado exitosamente a contabilidad",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message_code": "ACCOUNTING_TRANSFER_SENT",
                        "transfer_id": "90640c8a-2bd8-40fc-b652-e68b960a19e0",
                        "accounting_response": {
                            "success": True,
                            "exchangeId": "AF-2026-04-00001",
                            "batchId": 42,
                            "status": "RECEIVED"
                        }
                    }
                }
            },
        },
        400: {
            "description": "Solicitud inválida o configuración incorrecta del endpoint de contabilidad",
            "content": {
                "application/json": {
                    "examples": {
                        "external_project_required": {
                            "summary": "Proyecto externo obligatorio",
                            "value": {
                                "detail": {
                                    "code": "EXTERNAL_PROJECT_ID_REQUIRED",
                                    "meta": {}
                                }
                            }
                        },
                        "payload_required": {
                            "summary": "JSON normalizado obligatorio",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_TRANSFER_PAYLOAD_REQUIRED",
                                    "meta": {}
                                }
                            }
                        },
                        "endpoint_url_empty": {
                            "summary": "URL del endpoint de contabilidad vacía",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_TRANSFER_ENDPOINT_URL_EMPTY",
                                    "meta": {}
                                }
                            }
                        },
                        "endpoint_url_invalid": {
                            "summary": "URL del endpoint de contabilidad inválida",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_TRANSFER_ENDPOINT_URL_INVALID",
                                    "meta": {}
                                }
                            }
                        },
                        "method_required": {
                            "summary": "Método HTTP no configurado",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_TRANSFER_METHOD_TERM_REQUIRED",
                                    "meta": {}
                                }
                            }
                        },
                        "api_key_missing": {
                            "summary": "API key no configurada",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_TRANSFER_API_KEY_NOT_CONFIGURED",
                                    "meta": {}
                                }
                            }
                        },
                        "api_key_invalid_template": {
                            "summary": "Plantilla de API key inválida",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_TRANSFER_API_KEY_TEMPLATE_INVALID",
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
            "description": "El usuario no tiene permisos para transferir lotes contables",
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
        404: {
            "description": "No se encontró el endpoint de contabilidad configurado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "ACCOUNTING_TRANSFER_ENDPOINT_NOT_FOUND",
                            "meta": {}
                        }
                    }
                }
            },
        },
        502: {
            "description": "Error enviando el lote contable a contabilidad",
            "content": {
                "application/json": {
                    "examples": {
                        "send_error": {
                            "summary": "Error enviando lote",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_TRANSFER_SEND_ERROR",
                                    "meta": {}
                                }
                            }
                        },
                        "invalid_response": {
                            "summary": "Respuesta inválida de contabilidad",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_TRANSFER_INVALID_RESPONSE",
                                    "meta": {}
                                }
                            }
                        },
                        "exchange_id_required": {
                            "summary": "Contabilidad no retornó exchangeId",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_TRANSFER_EXCHANGE_ID_REQUIRED",
                                    "meta": {}
                                }
                            }
                        }
                    }
                }
            },
        },
    },
)
def transfer_accounting_batch(
    request: Request,
    payload: AccountingTransferRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ChecksService()

    ip = request.headers.get("x-forwarded-for")

    if ip:
        ip = ip.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    else:
        ip = None

    user_agent = request.headers.get("user-agent")

    return service.transfer_accounting_batch(
        db=db,
        payload=payload,
        current_user=current_user,
        ip=ip,
        user_agent=user_agent,
    )



@router.post(
    "/accounting-ACK",
    summary="Recibir confirmación de procesamiento de lote contable",
    description="""
        Endpoint público que recibe la confirmación (ACK) del procesamiento de un lote contable
        enviado previamente a contabilidad.

        Según el estado recibido:
        - Si status=PROCESSED: actualiza el lote como enviado y sus recibos de auditoría.
        - Si hay documentos fallidos: marca el lote como fallido y registra los errores por documento.

        Registra auditoría de la operación en af_audit_log.
    """,
    responses={
        200: {
            "description": "ACK procesado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message_code": "ACCOUNTING_ACK_PROCESSED",
                        "exchange_id": "AF-2026-04-00001"
                    }
                }
            },
        },
        400: {
            "description": "Payload de ACK inválido o exchangeId faltante",
            "content": {
                "application/json": {
                    "examples": {
                        "exchange_id_required": {
                            "summary": "ExchangeId obligatorio",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_ACK_EXCHANGE_ID_REQUIRED",
                                    "meta": {}
                                }
                            }
                        },
                        "status_required": {
                            "summary": "Status obligatorio",
                            "value": {
                                "detail": {
                                    "code": "ACCOUNTING_ACK_STATUS_REQUIRED",
                                    "meta": {}
                                }
                            }
                        }
                    }
                }
            },
        },
        404: {
            "description": "No se encontró el lote contable para el exchangeId recibido",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "ACCOUNTING_ACK_TRANSFER_NOT_FOUND",
                            "meta": {}
                        }
                    }
                }
            },
        },
    },
)
def accounting_ack(
    request: Request,
    payload: AccountingACKRequest,
    db: Session = Depends(get_db),
):
    service = ChecksService()

    ip = request.headers.get("x-forwarded-for")

    if ip:
        ip = ip.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    else:
        ip = None

    user_agent = request.headers.get("user-agent")

    return service.process_accounting_ack(
        db=db,
        payload=payload,
        ip=ip,
        user_agent=user_agent,
    )

router.include_router(vouchers_router)