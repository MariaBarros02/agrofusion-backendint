from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from datetime import date, datetime
from pydantic import BaseModel, Field


class ListChecksRequest(BaseModel):
    page_index: int = Field(1, description="Número de página a consultar", example=1)
    page_size: int = Field(5, description="Cantidad de registros por página", example=5)
    search: Optional[str] = Field(
        None,
        description="Texto de búsqueda por id, proyecto o emitido por",
        example="SIGMA"
    )
    state: Optional[str] = Field(
        None,
        description="Estado del comprobante",
        example="Fallido"
    )
    project_id: Optional[str] = Field(
        None,
        description="Identificador del proyecto origen",
        example="6f1f9f9c-7e84-4d8f-a7f7-123456789abc"
    )
    transaction_type: Optional[str] = Field(
        None,
        description="Tipo de comprobante",
        example="nomina contable"
    )
    start_date: Optional[datetime] = Field(
        None,
        description="Fecha inicial del rango de consulta",
        example="2026-03-01T00:00:00"
    )
    end_date: Optional[datetime] = Field(
        None,
        description="Fecha final del rango de consulta",
        example="2026-03-31T23:59:59"
    )


class CheckTypeOptionResponse(BaseModel):
    value: str = Field(
        ...,
        description="Valor interno normalizado del tipo",
        example="nomina contable"
    )
    label: str = Field(
        ...,
        description="Etiqueta visible del tipo",
        example="NOMINA CONTABLE"
    )


class CheckTypeListResponse(BaseModel):
    items: List[CheckTypeOptionResponse] = Field(
        ...,
        description="Lista de tipos únicos de comprobante"
    )


class CheckListItemResponse(BaseModel):
    id: str = Field(
        ...,
        description="Identificador único del comprobante",
        example="251f571"
    )
    accounting_entry_id: Optional[str] = Field(
        None,
        description="Identificador del asiento contable externo"
    )
    transaction_type: str = Field(
        ...,
        description="Tipo de comprobante",
        example="NOMINA CONTABLE"
    )
    project_name: Optional[str] = Field(
        None,
        description="Nombre del proyecto",
        example="SIGMA"
    )
    project_code: Optional[str] = Field(
        None,
        description="Código del proyecto",
        example="SIGMA"
    )
    state: str = Field(
        ...,
        description="Estado del comprobante",
        example="Fallido"
    )
    issued_at: Optional[datetime] = Field(
        None,
        description="Fecha de emisión",
        example="2026-03-27T10:30:00"
    )
    amount: Optional[float] = Field(
        None,
        description="Valor total del comprobante",
        example=2500000.0
    )
    issued_by: Optional[str] = Field(
        None,
        description="Usuario que emitió el comprobante",
        example="Carlos Pérez"
    )

    class Config:
        from_attributes = True


class CheckDetailResponse(CheckListItemResponse):
    queue_id: str = Field(..., description="Identificador de la cola contable")
    source_project_id: str = Field(..., description="Identificador del proyecto origen")
    source_module_code: Optional[str] = Field(None, description="Código del módulo origen")
    accounting_date: Optional[date] = Field(None, description="Fecha contable")
    sent_at: Optional[datetime] = Field(None, description="Fecha de envío")
    acknowledged_at: Optional[datetime] = Field(None, description="Fecha de acuse")
    accounting_entry_id: Optional[str] = Field(None, description="Identificador del asiento contable externo")
    response_json: Optional[Dict[str, Any]] = Field(None, description="Respuesta del sistema contable")
    payload_json: Dict[str, Any] = Field(..., description="Payload enviado al sistema contable")
    transaction_data: Dict[str, Any] = Field(..., description="Datos originales de la transacción")
    error_message: Optional[str] = Field(None, description="Mensaje de error del envío")
    retry_count: Optional[int] = Field(None, description="Cantidad de reintentos")
    queue_status: Optional[str] = Field(None, description="Estado de la cola")
    attempts: Optional[int] = Field(None, description="Intentos de la cola")
    max_attempts: Optional[int] = Field(None, description="Máximo de intentos")
    last_error: Optional[str] = Field(None, description="Último error de la cola")


class PaginatedChecksResponse(BaseModel):
    items: List[CheckListItemResponse] = Field(..., description="Listado de comprobantes")
    total: int = Field(..., description="Total de registros encontrados", example=25)
    page: int = Field(..., description="Página actual", example=1)
    size: int = Field(..., description="Cantidad de registros por página", example=5)
    total_pages: int = Field(..., description="Total de páginas disponibles", example=5)

    items: List[CheckListItemResponse] = Field(
        ...,
        description="Listado de comprobantes"
    )
    total: int = Field(
        ...,
        description="Total de registros encontrados",
        example=25
    )
    page: int = Field(
        ...,
        description="Página actual",
        example=1
    )
    size: int = Field(
        ...,
        description="Cantidad de registros por página",
        example=5
    )
    total_pages: int = Field(
        ...,
        description="Total de páginas disponibles",
        example=5
    )


class AccountingConsultRequest(BaseModel):
    external_project_id: str = Field(
        ...,
        description="Identificador del proyecto externo",
        example="6f1f9f9c-7e84-4d8f-a7f7-123456789abc"
    )
    external_endpoint_id: str = Field(
        ...,
        description="Identificador del endpoint externo configurado",
        example="9d8f9f9c-7e84-4d8f-a7f7-987654321abc"
    )
    sincePeriod: str = Field(
        ...,
        description="Fecha inicial del periodo de consulta",
        example="2025-04-01"
    )
    untilPeriod: str = Field(
        ...,
        description="Fecha final del periodo de consulta",
        example="2025-04-30"
    )


class AccountingRequestedPeriod(BaseModel):
    From: str = Field(
        ...,
        description="Fecha inicial solicitada",
        example="2025-04-01"
    )
    To: str = Field(
        ...,
        description="Fecha final solicitada",
        example="2025-04-30"
    )


class AccountingSourceSystem(BaseModel):
    SystemId: str = Field(
        ...,
        description="Identificador del sistema origen",
        example="disriego-prod-01"
    )
    SystemName: str = Field(
        ...,
        description="Nombre del sistema origen",
        example="Disriego"
    )
    SystemNIT: str = Field(
        ...,
        description="NIT del sistema origen",
        example="901724254"
    )
    Environment: str = Field(
        ...,
        description="Ambiente del sistema origen",
        example="production"
    )


class AccountingMetadata(BaseModel):
    ExchangeId: str = Field(
        ...,
        description="Identificador único del intercambio",
        example="AF-2026-04-000001"
    )
    GeneratedAt: str = Field(
        ...,
        description="Fecha de generación de la respuesta",
        example="2026-04-21T02:04:24.456911"
    )
    StandardVersion: str = Field(
        ...,
        description="Versión del estándar de intercambio",
        example="1.0"
    )
    RequestedPeriod: AccountingRequestedPeriod = Field(
        ...,
        description="Periodo solicitado"
    )
    SourceSystem: AccountingSourceSystem = Field(
        ...,
        description="Información del sistema origen"
    )
    GeneratedBy: str = Field(
        ...,
        description="Usuario o sistema que generó la respuesta",
        example="disriego-api"
    )


class AccountingSummary(BaseModel):
    TotalDocuments: int = Field(
        ...,
        description="Total de documentos encontrados",
        example=18
    )
    TotalInvoices: int = Field(
        ...,
        description="Total de facturas encontradas",
        example=12
    )
    TotalTransactions: int = Field(
        ...,
        description="Total de transacciones encontradas",
        example=6
    )
    TotalGrossAmount: float = Field(
        ...,
        description="Valor bruto total",
        example=2500000.0
    )
    TotalNet: float = Field(
        ...,
        description="Valor neto total",
        example=2300000.0
    )
    Currency: str = Field(
        ...,
        description="Moneda de los valores",
        example="COP"
    )


class AccountingDocumentType(BaseModel):
    Code: str = Field(
        ...,
        description="Código del tipo de documento",
        example="FV"
    )
    Name: str = Field(
        ...,
        description="Nombre del tipo de documento",
        example="Factura de venta"
    )


class AccountingInvoiceHeader(BaseModel):
    DocumentId: str = Field(
        ...,
        description="Identificador del documento",
        example="FV-001"
    )
    Prefix: str = Field(
        ...,
        description="Prefijo del documento",
        example="FV"
    )
    Serial: str = Field(
        ...,
        description="Número o serial del documento",
        example="001"
    )
    Type: AccountingDocumentType = Field(
        ...,
        description="Tipo de documento"
    )
    IssueDate: str = Field(
        ...,
        description="Fecha de emisión",
        example="2025-04-01"
    )
    DueDate: str = Field(
        ...,
        description="Fecha de vencimiento",
        example="2025-04-30"
    )
    Status: str = Field(
        ...,
        description="Estado del documento",
        example="Emitida"
    )
    UpdatedAt: str = Field(
        ...,
        description="Fecha de última actualización",
        example="2025-04-01T10:00:00"
    )


class AccountingThirdParty(BaseModel):
    NIT:Optional[str]  = Field(
        ...,
        description="Identificación tributaria del tercero",
        example="900123456"
    )
    Name: str = Field(
        ...,
        description="Nombre del tercero",
        example="Cliente de prueba"
    )
    Address: Optional[str] = Field(
        None,
        description="Dirección del tercero",
        example="Calle 123"
    )
    City: Optional[str] = Field(
        None,
        description="Ciudad del tercero",
        example="Neiva"
    )
    Country: Optional[str] = Field(
        None,
        description="País del tercero",
        example="Colombia"
    )
    Email: Optional[str] = Field(
        None,
        description="Correo electrónico del tercero",
        example="cliente@correo.com"
    )


class AccountingInvoiceTotals(BaseModel):
    Subtotal: float = Field(
        ...,
        description="Subtotal de la factura",
        example=1000000.0
    )
    TotalVAT: float = Field(
        ...,
        description="Total de IVA",
        example=190000.0
    )
    TotalWithholdings: float = Field(
        ...,
        description="Total de retenciones",
        example=0.0
    )
    TotalDiscounts: float = Field(
        ...,
        description="Total de descuentos",
        example=0.0
    )
    TotalPayment: float = Field(
        ...,
        description="Valor total a pagar",
        example=1190000.0
    )
    OutstandingBalance: float = Field(
        ...,
        description="Saldo pendiente",
        example=0.0
    )


class AccountingInvoiceLine(BaseModel):
    Code: str = Field(
        ...,
        description="Código del concepto o línea",
        example="SERV-001"
    )
    Name: str = Field(
        ...,
        description="Nombre del concepto o línea",
        example="Servicio de riego"
    )
    Description: str = Field(
        ...,
        description="Descripción de la línea",
        example="Servicio facturado"
    )
    LineType: str = Field(
        ...,
        description="Tipo de línea",
        example="service"
    )
    accounting_account: List[str] = Field(
        ...,
        description="Cuentas contables asociadas a la línea",
        example=["41013"]
    )
    Quantity: float = Field(
        ...,
        description="Cantidad facturada",
        example=1
    )
    UnitPrice: float = Field(
        ...,
        description="Valor unitario",
        example=1000000.0
    )
    Value: float = Field(
        ...,
        description="Valor total de la línea",
        example=1000000.0
    )
    Taxes: List[Any] = Field(
        default_factory=list,
        description="Listado de impuestos asociados a la línea",
        example=[]
    )


class AccountingInvoice(BaseModel):
    Header: AccountingInvoiceHeader = Field(
        ...,
        description="Encabezado de la factura"
    )
    ThirdParty: AccountingThirdParty = Field(
        ...,
        description="Información del tercero"
    )
    Totals: AccountingInvoiceTotals = Field(
        ...,
        description="Totales de la factura"
    )
    Lines: List[AccountingInvoiceLine] = Field(
        ...,
        description="Líneas o detalles de la factura"
    )


class AccountingPaymentMethod(BaseModel):
    Code: str = Field(
        ...,
        description="Código del medio de pago",
        example="TRANSFER"
    )


class AccountingTransaction(BaseModel):
    DocumentId: str = Field(
        ...,
        description="Identificador de la transacción",
        example="TRX-001"
    )
    Date: str = Field(
        ...,
        description="Fecha de la transacción",
        example="2025-04-15"
    )
    RelatedInvoiceId: str = Field(
        ...,
        description="Factura relacionada",
        example="FV-001"
    )
    ThirdParty: AccountingThirdParty = Field(
        ...,
        description="Información del tercero"
    )
    Amount: float = Field(
        ...,
        description="Valor de la transacción",
        example=1190000.0
    )
    Currency: str = Field(
        ...,
        description="Moneda de la transacción",
        example="COP"
    )
    Status: str = Field(
        ...,
        description="Estado de la transacción",
        example="Aplicado"
    )
    Notes: str = Field(
        ...,
        description="Notas de la transacción",
        example="Pago aplicado a factura"
    )
    UpdatedAt: str = Field(
        ...,
        description="Fecha de última actualización",
        example="2025-04-15T12:00:00"
    )
    Type: AccountingDocumentType = Field(
        ...,
        description="Tipo de transacción"
    )
    PaymentMethod: AccountingPaymentMethod = Field(
        ...,
        description="Método de pago"
    )


class AccountingConsultResponse(BaseModel):
    metadata: AccountingMetadata = Field(
        ...,
        description="Metadatos de la consulta contable"
    )
    summary: AccountingSummary = Field(
        ...,
        description="Resumen general de la consulta contable"
    )
    invoices: List[AccountingInvoice] = Field(
        ...,
        description="Listado de facturas"
    )
    transactions: List[AccountingTransaction] = Field(
        ...,
        description="Listado de transacciones"
    )


# ============================================================
# RF-INT-30 - Transferencia de lote contable a contabilidad
# ============================================================

class AccountingTransferRequest(BaseModel):
    external_project_id: str = Field(
        ...,
        description="Identificador del proyecto externo origen",
        example="6baa50f1-91e0-4eab-96bb-44b4ea380ddc"
    )
    external_endpoint_id: str = Field(
        ...,
        description="Identificador del endpoint externo",
        example="endpoint-001"
    )
    normalized_json: Dict[str, Any] = Field(
        ...,
        description="JSON normalizado recibido desde el proyecto externo y enviado a contabilidad",
        example={
            "metadata": {
                "ExchangeId": "AF-2026-04-000051",
                "GeneratedAt": "2026-04-14T10:00:00-05:00",
                "StandardVersion": "1.0",
                "RequestedPeriod": {
                    "From": "2025-05-01",
                    "To": "2025-05-31"
                },
                "SourceSystem": {
                    "SystemId": "disriego-prod-01",
                    "SystemName": "Disriego",
                    "SystemNIT": "900123456",
                    "Environment": "production"
                },
                "GeneratedBy": "agrofusion-integration-service"
            },
            "summary": {
                "TotalDocuments": 2,
                "TotalInvoices": 1,
                "TotalTransactions": 1,
                "TotalGrossAmount": 976500.0,
                "TotalNet": 976500.0,
                "Currency": "COP"
            },
            "invoices": [],
            "transactions": []
        }
    )


class AccountingTransferAccountingResponse(BaseModel):
    success: Optional[bool] = Field(
        None,
        description="Indica si contabilidad recibió correctamente el lote",
        example=True
    )
    exchangeId: Optional[str] = Field(
        None,
        description="Identificador del lote recibido por contabilidad",
        example="AF-2026-04-00001"
    )
    batchId: Optional[int] = Field(
        None,
        description="Identificador interno del lote en contabilidad",
        example=42
    )
    status: Optional[str] = Field(
        None,
        description="Estado inicial reportado por contabilidad",
        example="RECEIVED"
    )


class AccountingTransferResponse(BaseModel):
    success: bool = Field(
        ...,
        description="Indica si el envío del lote fue exitoso",
        example=True
    )
    message_code: str = Field(
        ...,
        description="Código internacionalizable para mostrar en frontend",
        example="ACCOUNTING_TRANSFER_SENT"
    )
    transfer_id: Optional[str] = Field(
        None,
        description="Identificador del lote registrado en af_accounting_transfers",
        example="90640c8a-2bd8-40fc-b652-e68b960a19e0"
    )
    accounting_response: AccountingTransferAccountingResponse = Field(
        ...,
        description="Respuesta recibida desde contabilidad"
    )


class ACKDocumentResult(BaseModel):
    documentId: str
    documentType: str
    status: str
    accountingEntryId: Optional[int] = None
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None


class AccountingACKRequest(BaseModel):
    exchangeId: str
    batchId: int
    status: str
    processedAt: Optional[str] = None
    processedDocuments: Optional[List[ACKDocumentResult]] = []
    failedDocuments: Optional[List[ACKDocumentResult]] = []


class AccountingACKResponse(BaseModel):
    success: bool
    message_code: str
    exchange_id: str



# ── Consulta de refresh ─────────────────────────────────────────────────────

class CheckRefreshRequest(BaseModel):
    """
    Body del endpoint POST /checks/{transfer_id}/refresh
    Solo necesita el transfer_id (viene en la URL), pero se define
    el schema por si en el futuro se requieren parámetros adicionales.
    No se necesita pasar nada: el periodo y el endpoint se leen del registro.
    """
    pass  # transfer_id viene en path; todo lo demás se obtiene de BD


# ── Elementos con indicación de cambio ─────────────────────────────────────

class InvoiceDiff(BaseModel):
    change_type: Literal["created", "modified", "deleted"] = Field(
        ...,
        description="Indica si la factura fue creada, modificada o eliminada",
        example="modified"
    )
    previous: Optional[Dict[str, Any]] = Field(
        None,
        description="Versión anterior de la factura (None si es nueva)"
    )
    current: Optional[Dict[str, Any]] = Field(
        None,
        description="Versión actual de la factura (None si fue eliminada)"
    )


class TransactionDiff(BaseModel):
    change_type: Literal["created", "modified", "deleted"] = Field(
        ...,
        description="Indica si la transacción fue creada, modificada o eliminada",
        example="created"
    )
    previous: Optional[Dict[str, Any]] = Field(
        None,
        description="Versión anterior de la transacción (None si es nueva)"
    )
    current: Optional[Dict[str, Any]] = Field(
        None,
        description="Versión actual de la transacción (None si fue eliminada)"
    )


# ── Respuesta del diff ──────────────────────────────────────────────────────

class CheckRefreshResponse(BaseModel):
    """
    Respuesta del endpoint de refresh/diff de comprobante.
    """
    has_changes: bool = Field(
        ...,
        description="Indica si existen diferencias entre el payload original y la nueva consulta",
        example=True
    )

    # metadata y summary completos de AMBAS versiones
    previous_metadata: Dict[str, Any] = Field(
        ...,
        description="Metadata del payload original almacenado en BD"
    )
    current_metadata: Dict[str, Any] = Field(
        ...,
        description="Metadata de la nueva consulta al endpoint externo"
    )
    previous_summary: Dict[str, Any] = Field(
        ...,
        description="Summary del payload original almacenado en BD"
    )
    current_summary: Dict[str, Any] = Field(
        ...,
        description="Summary de la nueva consulta al endpoint externo"
    )

    # Estado completo actual (todas las facturas/transacciones vigentes)
    current_invoices: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Lista completa de facturas en su estado actual (incluye las no modificadas). "
            "Se usa para reconstruir el payload_json completo al aplicar la actualización."
        )
    )
    current_transactions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Lista completa de transacciones en su estado actual (incluye las no modificadas). "
            "Se usa para reconstruir el payload_json completo al aplicar la actualización."
        )
    )

    # Solo las facturas/transacciones que cambiaron
    invoice_diffs: List[InvoiceDiff] = Field(
        default_factory=list,
        description=(
            "Facturas que fueron creadas, modificadas o eliminadas. "
            "Las facturas sin cambios NO se incluyen."
        )
    )
    transaction_diffs: List[TransactionDiff] = Field(
        default_factory=list,
        description=(
            "Transacciones que fueron creadas, modificadas o eliminadas. "
            "Las transacciones sin cambios NO se incluyen."
        )
    )



 
class AccountingUpdateRequest(BaseModel):
    """
    Body del endpoint POST /checks/{transfer_id}/update-accounting
    Recibe el diff generado por el endpoint de comparación.
    """
    diff: Dict[str, Any] = Field(
        ...,
        description="Objeto diff retornado por el endpoint de comparación (CheckRefreshResponse)",
        example={
            "has_changes": True,
            "previous_metadata": {},
            "current_metadata": {},
            "previous_summary": {},
            "current_summary": {},
            "invoice_diffs": [],
            "transaction_diffs": []
        }
    )
 
 
class AccountingUpdateResponse(BaseModel):
    """
    Respuesta del endpoint de actualización contable.
    """
    success: bool = Field(
        ...,
        description="Indica si la actualización fue enviada exitosamente",
        example=True
    )
    message_code: str = Field(
        ...,
        description="Código internacionalizable para mostrar en frontend",
        example="ACCOUNTING_UPDATE_SENT"
    )
    transfer_id: str = Field(
        ...,
        description="Identificador del comprobante actualizado (mismo transfer_id de entrada)",
        example="90640c8a-2bd8-40fc-b652-e68b960a19e0"
    )
    new_exchange_id: str = Field(
        ...,
        description="ExchangeId UPD generado y enviado a contabilidad",
        example="AF-UPD-2026-05-5261922"
    )
    accounting_response: Optional[Dict[str, Any]] = Field(
        None,
        description="Respuesta recibida desde contabilidad"
    )
    sent_payload: Optional[Dict[str, Any]] = Field(
        None,
        description="Payload AgroFusionExchangeUpdate enviado a contabilidad"
    )
