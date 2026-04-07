from datetime import datetime
from typing import List, Optional
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
    value: str = Field(..., description="Valor interno normalizado del tipo", example="nomina contable")
    label: str = Field(..., description="Etiqueta visible del tipo", example="NOMINA CONTABLE")


class CheckTypeListResponse(BaseModel):
    items: List[CheckTypeOptionResponse] = Field(
        ...,
        description="Lista de tipos únicos de comprobante"
    )


class CheckListItemResponse(BaseModel):
    id: str = Field(..., description="Identificador único del comprobante", example="251f571")
    transaction_type: str = Field(..., description="Tipo de comprobante", example="NOMINA CONTABLE")
    project_name: Optional[str] = Field(None, description="Nombre del proyecto", example="SIGMA")
    project_code: Optional[str] = Field(None, description="Código del proyecto", example="SIGMA")
    state: str = Field(..., description="Estado del comprobante", example="Fallido")
    issued_at: Optional[datetime] = Field(None, description="Fecha de emisión", example="2026-03-27T10:30:00")
    amount: Optional[float] = Field(None, description="Valor total del comprobante", example=2500000.0)
    issued_by: Optional[str] = Field(None, description="Usuario que emitió el comprobante", example="Carlos Pérez")

    class Config:
        from_attributes = True


class PaginatedChecksResponse(BaseModel):
    items: List[CheckListItemResponse] = Field(..., description="Listado de comprobantes")
    total: int = Field(..., description="Total de registros encontrados", example=25)
    page: int = Field(..., description="Página actual", example=1)
    size: int = Field(..., description="Cantidad de registros por página", example=5)
    total_pages: int = Field(..., description="Total de páginas disponibles", example=5)