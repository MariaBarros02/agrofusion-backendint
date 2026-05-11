import json
import math
from datetime import datetime
from pydoc import text
from uuid import uuid4
import random
import httpx
from fastapi import status
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.core.errors import int_error
from app.repositories.checks_repository import ChecksRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.checks import (
    AccountingACKRequest,
    AccountingACKResponse,
    ListChecksRequest,
    CheckDetailResponse,
    CheckListItemResponse,
    PaginatedChecksResponse,
    CheckTypeOptionResponse,
    CheckTypeListResponse,
    AccountingConsultRequest,
    AccountingConsultResponse,
    AccountingTransferRequest,
    AccountingTransferResponse,
    AccountingTransferAccountingResponse,
)
from app.services.permissions_service import PermissionsService


EXTERNAL_AUTH_CLIENT_ID = "agrofusion"
EXTERNAL_AUTH_CLIENT_SECRET = "super-secret-agrofusion-2026-usco"


class ChecksService:
    def __init__(self):
        self.repo = ChecksRepository()
        self.audit_repo = AuditRepository()
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
        """

        if not self.perm_service.validate_permission(
            db,
            current_user.get("role"),
            "034"
        ):
            int_error("AUTH_INSUFFICIENT_PERMISSIONS", status.HTTP_403_FORBIDDEN)

        if payload.page_index < 1:
            int_error("PAGE_INDEX_INVALID", status.HTTP_400_BAD_REQUEST)

        if payload.page_size < 1:
            int_error("PAGE_SIZE_INVALID", status.HTTP_400_BAD_REQUEST)

        rows, total = self.repo.get_list_checks(db, payload)

        total_pages = math.ceil(total / payload.page_size) if total else 1

        items = [
            CheckListItemResponse(
                id=str(row.id),
                transaction_type=row.transaction_type,
                project_name=row.project_name,
                accounting_entry_id=row.accounting_entry_id,
                project_code=row.project_code,
                state=row.state,
                issued_at=row.issued_at,
                amount=float(row.amount) if row.amount is not None else None,
                issued_by=row.issued_by,
            )
            for row in rows
        ]

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

    def consult_accounting(
        self,
        db: Session,
        payload: AccountingConsultRequest,
        current_user: dict,
        ip: str = None,
        user_agent: str = None
    ):
        """
        Consulta información contable desde el proyecto externo.
        """

        try:
            if not self.perm_service.validate_permission(
                db,
                current_user.get("role"),
                "042"
            ):
                int_error("AUTH_INSUFFICIENT_PERMISSIONS", status.HTTP_403_FORBIDDEN)

            if not payload.external_project_id or not payload.external_project_id.strip():
                int_error("EXTERNAL_PROJECT_ID_REQUIRED", status.HTTP_400_BAD_REQUEST)

            if not payload.external_endpoint_id or not payload.external_endpoint_id.strip():
                int_error("EXTERNAL_ENDPOINT_ID_REQUIRED", status.HTTP_400_BAD_REQUEST)

            if not payload.sincePeriod or not payload.sincePeriod.strip():
                int_error("SINCE_PERIOD_REQUIRED", status.HTTP_400_BAD_REQUEST)

            if not payload.untilPeriod or not payload.untilPeriod.strip():
                int_error("UNTIL_PERIOD_REQUIRED", status.HTTP_400_BAD_REQUEST)

            self._validate_accounting_period(
                payload.sincePeriod,
                payload.untilPeriod
            )

            endpoint_config = self.repo.get_accounting_consult_endpoint(
                db,
                payload.external_project_id,
                payload.external_endpoint_id
            )

            if endpoint_config is None:
                int_error("EXTERNAL_ENDPOINT_NOT_FOUND", status.HTTP_404_NOT_FOUND)
            print("ENDPOINT: ", payload.external_endpoint_id)
            overlapping_transfer = self.repo.get_overlapping_accounting_transfer_period(
                db,
                payload.external_project_id,
                payload.external_endpoint_id,
                payload.sincePeriod,
                payload.untilPeriod
            )

            if overlapping_transfer is not None:
                int_error(
                    "ACCOUNTING_TRANSFER_PERIOD_ALREADY_EXISTS",
                    status.HTTP_409_CONFLICT
                )

            http_method = self._get_value(
                endpoint_config,
                "http_method",
                "method",
                "request_method"
            )

            if http_method and str(http_method).upper().strip() != "GET":
                int_error("EXTERNAL_ENDPOINT_METHOD_INVALID", status.HTTP_400_BAD_REQUEST)

            url_template = self._get_value(
                endpoint_config,
                "url",
                "endpoint_url",
                "base_url"
            )

            if not url_template:
                int_error("EXTERNAL_ENDPOINT_URL_EMPTY", status.HTTP_400_BAD_REQUEST)

            url = self._build_accounting_consult_url(
                str(url_template),
                payload.sincePeriod,
                payload.untilPeriod
            )

            headers = self._build_external_endpoint_headers(endpoint_config)

            is_protected = self._is_truthy(
                self._get_value(endpoint_config, "is_protected")
            )

            if is_protected:
                external_token = self._request_external_service_token(
                    db=db,
                    payload=payload,
                    current_user=current_user
                )

                headers["Authorization"] = f"Bearer {external_token}"

            safe_headers = dict(headers)

            if "Authorization" in safe_headers:
                safe_headers["Authorization"] = "Bearer ***"

            print("==============================================")
            print("CONSULTA CONTABLE EXTERNA")
            print("URL TEMPLATE:", url_template)
            print("URL FINAL:", url)
            print("IS_PROTECTED:", is_protected)
            print("HEADERS:", safe_headers)
            print("==============================================")

            try:
                response = httpx.get(
                    url,
                    headers=headers,
                    timeout=60.0,
                    trust_env=False
                )

            except httpx.TimeoutException as ex:
                print("TIMEOUT ENDPOINT EXTERNO:", type(ex).__name__)
                print("DETALLE:", str(ex))
                print("URL:", url)

                self._raise_external_accounting_consult_error(
                    db=db,
                    payload=payload,
                    payload_excerpt={
                        "status": "N/A",
                        "data": "N/A"
                    }
                )

            except httpx.RequestError as ex:
                print("ERROR CONSUMIENDO ENDPOINT EXTERNO:", type(ex).__name__)
                print("DETALLE:", str(ex))
                print("URL:", url)

                self._raise_external_accounting_consult_error(
                    db=db,
                    payload=payload,
                    payload_excerpt={
                        "status": "N/A",
                        "data": "N/A"
                    }
                )

            except Exception as ex:
                print("ERROR NO CONTROLADO CONSUMIENDO ENDPOINT EXTERNO:", type(ex).__name__)
                print("DETALLE:", str(ex))
                print("URL:", url)

                self._raise_external_accounting_consult_error(
                    db=db,
                    payload=payload,
                    payload_excerpt={
                        "status": "N/A",
                        "data": "N/A"
                    }
                )

            if response.status_code < 200 or response.status_code >= 300:
                print("ENDPOINT EXTERNO RESPONDIÓ ERROR")
                print("STATUS CODE:", response.status_code)
                print("RESPONSE TEXT:", response.text)
                print("URL:", url)

                self._raise_external_accounting_consult_error(
                    db=db,
                    payload=payload,
                    payload_excerpt=self._get_external_response_payload_excerpt(response)
                )

            try:
                data = response.json()
            except ValueError:
                print("ENDPOINT EXTERNO NO DEVOLVIÓ JSON VÁLIDO")
                print("RESPONSE TEXT:", response.text)
                print("URL:", url)

                self._raise_external_accounting_consult_error(
                    db=db,
                    payload=payload,
                    payload_excerpt=self._get_external_response_payload_excerpt(response)
                )

            try:
                result = AccountingConsultResponse(**data)


                random_suffix = f"{random.randint(0, 9999999):07d}"
                current_exchange_id = result.metadata.ExchangeId
                parts = current_exchange_id.split("-")
                parts[-1] = random_suffix

                result.metadata.ExchangeId = "-".join(parts)

                # #PRUEBAAA
                result.metadata.SourceSystem.SystemNIT = "9001766666"

            except Exception as ex:
                print("RESPUESTA EXTERNA NO CUMPLE EL CONTRATO ESPERADO")
                print("ERROR:", type(ex).__name__)
                print("DETALLE:", str(ex))
                print("DATA:", data)

                self._raise_external_accounting_consult_error(
                    db=db,
                    payload=payload,
                    payload_excerpt={
                        "status": response.status_code if response is not None else "N/A",
                        "data": data if data else "N/A"
                    }
                )

            self._log_accounting_info_consult_audit(
                db=db,
                current_user=current_user,
                payload=payload,
                outcome="success",
                ip=ip,
                user_agent=user_agent
            )

            return result

        except Exception:
            self._log_accounting_info_consult_audit(
                db=db,
                current_user=current_user,
                payload=payload,
                outcome="failure",
                ip=ip,
                user_agent=user_agent
            )

            raise

    def transfer_accounting_batch(
        self,
        db: Session,
        payload: AccountingTransferRequest,
        current_user: dict,
        ip: str = None,
        user_agent: str = None
    ):
        """
        Envía el JSON normalizado a contabilidad y registra el lote como processing.

        MODO SIMULACIÓN:
        La llamada real al endpoint externo de contabilidad queda comentada porque
        actualmente el servicio externo está caído. Se simula una respuesta exitosa
        con la estructura esperada por el requerimiento.

        Nota:
        af_accounting_transfers.accounting_entry_id espera UUID, por eso en simulación
        se genera un UUID válido para exchangeId.
        """

        try:
            if not self.perm_service.validate_permission(
                db,
                current_user.get("role"),
                "043"
            ):
                print('Sin permiso')
                int_error("AUTH_INSUFFICIENT_PERMISSIONS", status.HTTP_403_FORBIDDEN)

            if not payload.external_project_id or not payload.external_project_id.strip():
                int_error("EXTERNAL_PROJECT_ID_REQUIRED", status.HTTP_400_BAD_REQUEST)

            if not payload.normalized_json:
                int_error("ACCOUNTING_TRANSFER_PAYLOAD_REQUIRED", status.HTTP_400_BAD_REQUEST)

            transfer_endpoint = self.repo.get_accounting_transfer_endpoint(
                db=db,
                external_project_id= payload.external_project_id,
            )


            if transfer_endpoint is None:
                int_error("ACCOUNTING_TRANSFER_ENDPOINT_NOT_FOUND", status.HTTP_404_NOT_FOUND)

            url = self._get_value(transfer_endpoint, "url")

            if not url:
                int_error("ACCOUNTING_TRANSFER_ENDPOINT_URL_EMPTY", status.HTTP_400_BAD_REQUEST)

            if not str(url).lower().startswith("http://") and not str(url).lower().startswith("https://"):
                print("URL CONTABILIDAD SIN PROTOCOLO:", url)
                int_error("ACCOUNTING_TRANSFER_ENDPOINT_URL_INVALID", status.HTTP_400_BAD_REQUEST)

            method_term_id = self._get_value(transfer_endpoint, "method_term_id")

            if not method_term_id:
                int_error("ACCOUNTING_TRANSFER_METHOD_TERM_REQUIRED", status.HTTP_400_BAD_REQUEST)

            method_value = self.repo.get_cat_term_value(
                db=db,
                term_id=str(method_term_id)
            )

            http_method = self._normalize_http_method(method_value)

            api_key_template = (
                self._get_value(transfer_endpoint, "response_template")
                or self._get_value(transfer_endpoint, "params_template")
                or self._get_value(transfer_endpoint, "body_template")
            )

            print("==============================================")
            print("TEMPLATE API KEY RESUELTO")
            print("RESPONSE_TEMPLATE:", self._get_value(transfer_endpoint, "response_template"))
            print("PARAMS_TEMPLATE:", self._get_value(transfer_endpoint, "params_template"))
            print("BODY_TEMPLATE:", self._get_value(transfer_endpoint, "body_template"))
            print("API_KEY_TEMPLATE_USADO:", api_key_template)
            print("==============================================")

            api_key_headers = self._build_accounting_transfer_api_key_headers(
                api_key_template
            )

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                **api_key_headers,
            }

            safe_headers = dict(headers)

            for secret_header in ["x-api-key", "X-API-Key", "Authorization"]:
                if secret_header in safe_headers:
                    safe_headers[secret_header] = "***"

            print("==============================================")
            print("ENVIANDO LOTE CONTABLE A CONTABILIDAD")
            print("MODO: SIMULACIÓN")
            print("URL:", url)
            print("METHOD:", http_method)
            print("HEADERS:", safe_headers)
            print("EXTERNAL_PROJECT_ID:", payload.external_project_id)
            print("==============================================")

            # ============================================================
            # LLAMADA REAL AL ENDPOINT DE CONTABILIDAD
            # Comentada temporalmente porque el servicio externo está caído.
            # Cuando SIGCON vuelva a estar disponible:
            # 1. Descomentar este bloque.
            # 2. Eliminar o comentar el bloque de respuesta simulada.
            # ============================================================

            try:
                response = httpx.request(
                    method=http_method,
                    url=str(url),
                    json=payload.normalized_json,
                    headers=headers,
                    timeout=60.0,
                    trust_env=False
                )
            
            except httpx.TimeoutException as ex:
                print("TIMEOUT ENVIANDO LOTE A CONTABILIDAD:", type(ex).__name__)
                print("DETALLE:", str(ex))
                print("URL:", url)
            
                int_error("ACCOUNTING_TRANSFER_SEND_ERROR", status.HTTP_502_BAD_GATEWAY, meta={
                    "error_type": type(ex).__name__,
                    "detail": str(ex),
                    "url": url,
                    "external_response": None  # No hay respuesta porque fue timeout
                })
            
            except httpx.RequestError as ex:
                print("ERROR ENVIANDO LOTE A CONTABILIDAD:", type(ex).__name__)
                print("DETALLE:", str(ex))
                print("URL:", url)
            
                 # Intentar parsear la respuesta como JSON si es posible
                external_response_data = None
                try:
                    external_response_data = response.json()
                except:
                    external_response_data = {"raw_text": response.text}
                
                int_error(
                    "ACCOUNTING_TRANSFER_SEND_ERROR", 
                    status.HTTP_502_BAD_GATEWAY,
                    meta=external_response_data
                    
                )
            
            except Exception as ex:
                print("ERROR NO CONTROLADO ENVIANDO LOTE A CONTABILIDAD:", type(ex).__name__)
                print("DETALLE:", str(ex))
                print("URL:", url)

                # Intentar parsear la respuesta como JSON si es posible
                external_response_data = None
                try:
                    external_response_data = response.json()
                except:
                    external_response_data = {"raw_text": response.text}
                
                int_error(
                    "ACCOUNTING_TRANSFER_SEND_ERROR", 
                    status.HTTP_502_BAD_GATEWAY,
                    meta=external_response_data
                    
                )
            
            if response.status_code < 200 or response.status_code >= 300:
                print("CONTABILIDAD RESPONDIÓ ERROR")
                print("STATUS CODE:", response.status_code)
                print("RESPONSE TEXT:", response.text)

                # Intentar parsear la respuesta como JSON si es posible
                external_response_data = None
                try:
                    external_response_data = response.json()
                except:
                    external_response_data = {"raw_text": response.text}
                
                int_error(
                    "ACCOUNTING_TRANSFER_SEND_ERROR", 
                    status.HTTP_502_BAD_GATEWAY,
                    meta=external_response_data
                    
                )
                        
            try:
                accounting_response_data = response.json()
                print
            except ValueError:
                print("CONTABILIDAD NO DEVOLVIÓ JSON VÁLIDO")
                print("STATUS CODE:", response.status_code)
                print("RESPONSE TEXT:", response.text)
            
                int_error("ACCOUNTING_TRANSFER_INVALID_RESPONSE", status.HTTP_502_BAD_GATEWAY)

            # # ============================================================
            # # RESPUESTA SIMULADA SEGÚN REQUERIMIENTO
            # # ============================================================

            # metadata = payload.normalized_json.get("metadata") or {}
            # original_exchange_id = metadata.get("ExchangeId")

            # # La BD espera UUID en af_accounting_transfers.accounting_entry_id.
            # # Por eso la simulación devuelve un UUID válido como exchangeId.
            # simulated_exchange_id =  original_exchange_id
            # simulated_batch_id = int(datetime.utcnow().strftime("%H%M%S"))

            # accounting_response_data = {
            #     "success": True,
            #     "exchangeId": simulated_exchange_id,
            #     "batchId": simulated_batch_id,
            #     "status": "RECEIVED"
            # }

            # print("==============================================")
            # print("RESPUESTA SIMULADA DE CONTABILIDAD")
            # print("EXCHANGE ID ORIGINAL DEL JSON:", original_exchange_id)
            # print("EXCHANGE ID SIMULADO UUID PARA BD:", simulated_exchange_id)
            # print("DATA:", accounting_response_data)
            # print("==============================================")

            try:
                accounting_response = AccountingTransferAccountingResponse(
                    **accounting_response_data
                )
                print("RESPUESTA DE CONTABILIDAD PARSEADA CON ÉXITO")
            except Exception as ex:
                print("RESPUESTA DE CONTABILIDAD NO CUMPLE EL CONTRATO ESPERADO")
                print("ERROR:", type(ex).__name__)
                print("DETALLE:", str(ex))
                print("DATA:", accounting_response_data)

                int_error("ACCOUNTING_TRANSFER_INVALID_RESPONSE", status.HTTP_502_BAD_GATEWAY)

            if accounting_response.success is False:
                print("CONTABILIDAD REPORTÓ RESPUESTA NEGATIVA")
                print("DATA:", accounting_response_data)
                 # Intentar parsear la respuesta como JSON si es posible
                external_response_data = None
                try:
                    external_response_data = response.json()
                except:
                    external_response_data = {"raw_text": response.text}
                
                int_error(
                    "ACCOUNTING_TRANSFER_SEND_ERROR", 
                    status.HTTP_502_BAD_GATEWAY,
                    meta=external_response_data
                    
                )

            exchange_id = accounting_response.exchangeId

            if not exchange_id:
                int_error("ACCOUNTING_TRANSFER_EXCHANGE_ID_REQUIRED", status.HTTP_502_BAD_GATEWAY)

            endpoint_name = (
                self._get_value(transfer_endpoint, "endpoint_name")
                or "Accounting transfer"
            )
            actor_id = self._get_actor_id(current_user)
            endpoint_config = self.repo.get_accounting_consult_endpoint(
                db,
                payload.external_project_id,
                payload.external_endpoint_id
            )

            queue_id = self.repo.create_accounting_queue(
                db=db,
                source_project_id=payload.external_project_id,
                source_module_code=endpoint_config["endpoint_name"],
                transaction_type=endpoint_config["endpoint_name"],
                transaction_data=payload.normalized_json,
                user_id=actor_id
            )
           
            transfer_id = self.repo.create_accounting_transfer(
                db=db,
                queue_id=str(queue_id),
                external_project_id=payload.external_project_id,
                external_endpoint_id= payload.external_endpoint_id,
                transaction_type=endpoint_config["endpoint_name"],
                payload_json=payload.normalized_json,
                accounting_entry_id=exchange_id
            )

            self.repo.create_accounting_audit_receipts(
                db=db,
                accounting_transfer_id=str(transfer_id),
                accounting_entry_id=exchange_id,
                normalized_json=payload.normalized_json
            )

            db.commit()

            self._log_accounting_transfer_audit(
                db=db,
                current_user=current_user,
                payload=payload,
                outcome="success",
                ip=ip,
                user_agent=user_agent
            )

            return AccountingTransferResponse(
                success=True,
                message_code="ACCOUNTING_TRANSFER_SENT",
                transfer_id=str(transfer_id),
                accounting_response=accounting_response
            )

        except Exception:
            db.rollback()

            self._log_accounting_transfer_audit(
                db=db,
                current_user=current_user,
                payload=payload,
                outcome="failure",
                ip=ip,
                user_agent=user_agent
            )

            raise
    def process_accounting_ack(
        self,
        db: Session,
        payload: AccountingACKRequest,
        ip: str = None,
        user_agent: str = None,
    ):
        try:
            # ── 1. Validaciones ────────────────────────────────────────────
            if not payload.exchangeId or not payload.exchangeId.strip():
                int_error("ACCOUNTING_ACK_EXCHANGE_ID_REQUIRED", status.HTTP_400_BAD_REQUEST)

            if not payload.status or not payload.status.strip():
                int_error("ACCOUNTING_ACK_STATUS_REQUIRED", status.HTTP_400_BAD_REQUEST)

            # ── 2. Buscar lote ─────────────────────────────────────────────
            transfer = self.repo.get_accounting_transfer_by_exchange_id(
                db=db,
                exchange_id=payload.exchangeId,
            )

            if transfer is None:
                int_error("ACCOUNTING_ACK_TRANSFER_NOT_FOUND", status.HTTP_404_NOT_FOUND)

            transfer_id  = str(transfer.transfer_id)
            ack_status   = payload.status.upper()
            has_failures = bool(payload.failedDocuments)
            now          = datetime.utcnow()
            ack_payload  = payload.dict()

            # ── 3. Procesar resultado ──────────────────────────────────────
            if ack_status == "PROCESSED" and not has_failures:
                # ── 3a. Lote 100% exitoso ──────────────────────────────
                transfer_status = "sent"

                self.repo.update_accounting_transfer_ack(
                    db=db,
                    transfer_id=transfer_id,
                    transfer_status=transfer_status,
                    acknowledged_at=now,
                    response_json=ack_payload,
                )
                self.repo.update_accounting_queue_status(
                    db=db,
                    transfer_id=transfer_id,
                    queue_status=transfer_status,
                    processed_at=now,                    # ← nuevo
                )
                self.repo.update_audit_receipts_status(
                    db=db,
                    accounting_transfer_id=transfer_id,
                    status="sent",
                )
                outcome      = "success"
                message_code = "ACCOUNTING_ACK_PROCESSED"

            elif ack_status == "PARTIAL" or (ack_status == "PROCESSED" and has_failures):
                # ── 3b. Lote PARTIAL ──────────────────────────────────
                transfer_status = "partial"

                self.repo.update_accounting_transfer_ack(
                    db=db,
                    transfer_id=transfer_id,
                    transfer_status=transfer_status,
                    acknowledged_at=now,
                    response_json=ack_payload,
                )
                self.repo.update_accounting_queue_status(
                    db=db,
                    transfer_id=transfer_id,
                    queue_status=transfer_status,
                    processed_at=now,                    # ← nuevo
                )

                # Documentos exitosos → sent
                for doc in (payload.processedDocuments or []):
                    self.repo.update_audit_receipt_sent(
                        db=db,
                        accounting_transfer_id=transfer_id,
                        document_id=doc.documentId,
                    )

                # Documentos fallidos → failed + error_log con fragmento completo del ACK
                for failed_doc in (payload.failedDocuments or []):
                    self.repo.update_audit_receipt_failed(
                        db=db,
                        accounting_transfer_id=transfer_id,
                        document_id=failed_doc.documentId,
                        failed_at=now,
                        error_log={                          # fragmento exacto del ACK
                            "documentId":       failed_doc.documentId,
                            "documentType":     failed_doc.documentType,
                            "status":           failed_doc.status,
                            "accountingEntryId": failed_doc.accountingEntryId,
                            "errorCode":        failed_doc.errorCode,
                            "errorMessage":     failed_doc.errorMessage,
                        },
                    )

                outcome      = "partial"
                message_code = "ACCOUNTING_ACK_PARTIAL"

            else:
                # ── 3c. Lote FAILED ───────────────────────────────────
                transfer_status = "failed"

                self.repo.update_accounting_transfer_ack(
                    db=db,
                    transfer_id=transfer_id,
                    transfer_status=transfer_status,
                    acknowledged_at=now,
                    response_json=ack_payload,
                )
                self.repo.update_accounting_queue_status(
                    db=db,
                    transfer_id=transfer_id,
                    queue_status=transfer_status,
                    processed_at=now,                    # ← nuevo
                )

                # Todos fallidos → failed + error_log con fragmento completo del ACK
                for failed_doc in (payload.failedDocuments or []):
                    self.repo.update_audit_receipt_failed(
                        db=db,
                        accounting_transfer_id=transfer_id,
                        document_id=failed_doc.documentId,
                        failed_at=now,
                        error_log={                          # fragmento exacto del ACK
                            "documentId":       failed_doc.documentId,
                            "documentType":     failed_doc.documentType,
                            "status":           failed_doc.status,
                            "accountingEntryId": failed_doc.accountingEntryId,
                            "errorCode":        failed_doc.errorCode,
                            "errorMessage":     failed_doc.errorMessage,
                        },
                    )

                outcome      = "failure"
                message_code = "ACCOUNTING_ACK_FAILED"
            db.commit()

            # ── 4. Auditoría ───────────────────────────────────────────────
            self._log_accounting_ack_audit(
                db=db,
                transfer=transfer,
                exchange_id=payload.exchangeId,
                outcome=outcome,
                ip=ip,
                user_agent=user_agent,
            )

            return AccountingACKResponse(
                success=True,
                message_code=message_code,
                exchange_id=payload.exchangeId,
            )

        except Exception:
            db.rollback()
            self._log_accounting_ack_audit(
                db=db,
                transfer=None,
                exchange_id=getattr(payload, "exchangeId", None),
                outcome="failure",
                ip=ip,
                user_agent=user_agent,
            )
            raise
    def update_audit_receipt_sent(
        self,
        db: Session,
        accounting_transfer_id: str,
        document_id: str,
    ):
        """
        Marca como 'sent' el af_audit_receipt cuyo payload->>'documentId'
        coincida con document_id. Se usa en lotes PARTIAL para los documentos
        que sí fueron procesados exitosamente.
        """
        query = text("""
            UPDATE public.af_audit_receipts
            SET status = 'sent'
            WHERE
                accounting_transfer_id = CAST(:accounting_transfer_id AS uuid)
                AND payload->>'documentId' = :document_id
        """)

        result = db.execute(query, {
            "accounting_transfer_id": accounting_transfer_id,
            "document_id": document_id,
        })

        print("==============================================")
        print("af_audit_receipt MARCADO COMO SENT (PARCIAL)")
        print("ACCOUNTING_TRANSFER_ID:", accounting_transfer_id)
        print("DOCUMENT_ID:", document_id)
        print("FILAS AFECTADAS:", result.rowcount)
        print("==============================================")

        
    def _log_accounting_ack_audit(
        self,
        db: Session,
        transfer,
        exchange_id: str,
        outcome: str,
        ip: str = None,
        user_agent: str = None,
    ):
        try:
            project = self.audit_repo.get_project_by_code(db, code="AGROFUSION")

            # El ACK es público, no hay usuario autenticado
            # Se usa un actor_id neutro (None o un sistema)
            self.audit_repo.log_event(
                db=db,
                action_code="ACCOUNTING_ACK",
                outcome=outcome,
                module_code="ACCOUNTING_VOUCHERS",
                project_id=project.af_project_id,
                actor_id=None,
                ip=ip,
                user_agent=user_agent,
                metadata={
                    "external_project": (
                        str(transfer.source_project_id)
                        if transfer is not None
                        else None
                    ),
                    "ExchangeId": exchange_id,
                },
            )
        except Exception as audit_ex:
            # La auditoría nunca debe tumbar el flujo principal
            print("ERROR REGISTRANDO AUDITORÍA ACK:", type(audit_ex).__name__, str(audit_ex))

    def _validate_accounting_period(
        self,
        since_period: str,
        until_period: str
    ):
        try:
            since = datetime.strptime(since_period.strip(), "%Y-%m-%d").date()
            until = datetime.strptime(until_period.strip(), "%Y-%m-%d").date()
        except ValueError:
            int_error("ACCOUNTING_PERIOD_FORMAT_INVALID", status.HTTP_400_BAD_REQUEST)

        if since > until:
            int_error("ACCOUNTING_PERIOD_RANGE_INVALID", status.HTTP_400_BAD_REQUEST)

    def _build_accounting_consult_url(
        self,
        url_template: str,
        since_period: str,
        until_period: str
    ) -> str:
        url = (
            url_template
            .replace("{sincePeriod}", since_period.strip())
            .replace("{untilPeriod}", until_period.strip())
        )

        if "{sincePeriod}" in url or "{untilPeriod}" in url:
            int_error("EXTERNAL_ENDPOINT_URL_TEMPLATE_INVALID", status.HTTP_400_BAD_REQUEST)

        if not url.lower().startswith("http://") and not url.lower().startswith("https://"):
            print("URL SIN PROTOCOLO:", url)
            int_error("EXTERNAL_ENDPOINT_URL_INVALID", status.HTTP_400_BAD_REQUEST)

        return url

    def _build_external_endpoint_headers(self, endpoint_config) -> dict:
        headers = {
            "Accept": "application/json"
        }

        authorization_type = self._get_value(
            endpoint_config,
            "authorization_type",
            "auth_type"
        )

        authorization_value = self._get_value(
            endpoint_config,
            "authorization_value",
            "auth_value",
            "token",
            "api_key"
        )

        if not authorization_type or not authorization_value:
            return headers

        auth_type = str(authorization_type).lower().strip()
        auth_value = str(authorization_value).strip()

        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {auth_value}"

        elif auth_type == "api_key":
            headers["x-api-key"] = auth_value

        elif auth_type == "basic":
            headers["Authorization"] = f"Basic {auth_value}"

        return headers

    def _build_accounting_transfer_api_key_headers(self, response_template) -> dict:
        """
        Extrae la API key desde la configuración del endpoint.
        """

        if not response_template:
            int_error("ACCOUNTING_TRANSFER_API_KEY_NOT_CONFIGURED", status.HTTP_400_BAD_REQUEST)

        template = response_template

        if isinstance(template, str):
            try:
                template = json.loads(template)
            except ValueError:
                int_error("ACCOUNTING_TRANSFER_API_KEY_TEMPLATE_INVALID", status.HTTP_400_BAD_REQUEST)

        if not isinstance(template, dict):
            int_error("ACCOUNTING_TRANSFER_API_KEY_TEMPLATE_INVALID", status.HTTP_400_BAD_REQUEST)

        headers = template.get("headers")

        if isinstance(headers, dict) and headers:
            return {
                str(key): str(value)
                for key, value in headers.items()
            }

        header_name = (
            template.get("header_name")
            or template.get("header")
            or template.get("key_name")
            or template.get("name")
            or "x-api-key"
        )

        api_key = (
            template.get("api_key")
            or template.get("apikey")
            or template.get("apiKey")
            or template.get("x-api-key")
            or template.get("X-API-Key")
            or template.get("value")
            or template.get("token")
        )

        if not api_key:
            print("==============================================")
            print("NO SE ENCONTRÓ API KEY EN TEMPLATE")
            print("TEMPLATE:", template)
            print("==============================================")

            int_error("ACCOUNTING_TRANSFER_API_KEY_NOT_CONFIGURED", status.HTTP_400_BAD_REQUEST)

        return {
            str(header_name): str(api_key)
        }

    def _request_external_service_token(
        self,
        db: Session,
        payload: AccountingConsultRequest,
        current_user: dict
    ) -> str:
        auth_endpoint_config = self.repo.get_external_service_token_endpoint(
            db=db,
            external_project_id=payload.external_project_id
        )

        if auth_endpoint_config is None:
            int_error("EXTERNAL_AUTH_ENDPOINT_NOT_FOUND", status.HTTP_404_NOT_FOUND)

        auth_url = self._get_value(auth_endpoint_config, "url")

        if not auth_url:
            int_error("EXTERNAL_AUTH_ENDPOINT_URL_EMPTY", status.HTTP_400_BAD_REQUEST)

        if not auth_url.lower().startswith("http://") and not auth_url.lower().startswith("https://"):
            print("URL TOKEN SIN PROTOCOLO:", auth_url)
            int_error("EXTERNAL_AUTH_ENDPOINT_URL_INVALID", status.HTTP_400_BAD_REQUEST)

        method_term_id = self._get_value(auth_endpoint_config, "method_term_id")

        if not method_term_id:
            int_error("EXTERNAL_AUTH_METHOD_TERM_REQUIRED", status.HTTP_400_BAD_REQUEST)

        method_value = self.repo.get_cat_term_value(
            db=db,
            term_id=str(method_term_id)
        )

        http_method = self._normalize_http_method(method_value)

        email = self._get_current_user_email(current_user)

        print("EMAIL USUARIO ACTUAL:", email)

        if not email:
            int_error("EXTERNAL_AUTH_USER_EMAIL_REQUIRED", status.HTTP_400_BAD_REQUEST)

        body = {
            "client_id": EXTERNAL_AUTH_CLIENT_ID,
            "client_secret": EXTERNAL_AUTH_CLIENT_SECRET,
            "email": email,
        }

        print("==============================================")
        print("SOLICITANDO TOKEN EXTERNO")
        print("URL TOKEN:", auth_url)
        print("METHOD:", http_method)
        print("EMAIL:", email)
        print("==============================================")

        try:
            response = httpx.request(
                method=http_method,
                url=auth_url,
                json=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
                trust_env=False
            )

        except httpx.TimeoutException as ex:
            print("TIMEOUT SOLICITANDO TOKEN EXTERNO:", type(ex).__name__)
            print("DETALLE:", str(ex))
            print("URL:", auth_url)

            self._raise_external_accounting_consult_error(
                db=db,
                payload=payload,
                payload_excerpt={
                    "status": "N/A",
                    "data": "N/A"
                }
            )

        except httpx.RequestError as ex:
            print("ERROR SOLICITANDO TOKEN EXTERNO:", type(ex).__name__)
            print("DETALLE:", str(ex))
            print("URL:", auth_url)

            self._raise_external_accounting_consult_error(
                db=db,
                payload=payload,
                payload_excerpt={
                    "status": "N/A",
                    "data": "N/A"
                }
            )

        if response.status_code < 200 or response.status_code >= 300:
            print("ENDPOINT TOKEN EXTERNO RESPONDIÓ ERROR")
            print("STATUS CODE:", response.status_code)
            print("RESPONSE TEXT:", response.text)

            self._raise_external_accounting_consult_error(
                db=db,
                payload=payload,
                payload_excerpt=self._get_external_response_payload_excerpt(response)
            )

        try:
            token_response_data = response.json()
        except ValueError:
            print("ENDPOINT TOKEN EXTERNO NO DEVOLVIÓ JSON VÁLIDO")
            print("RESPONSE TEXT:", response.text)

            self._raise_external_accounting_consult_error(
                db=db,
                payload=payload,
                payload_excerpt=self._get_external_response_payload_excerpt(response)
            )

        token = self._extract_token_from_external_response(
            token_response_data=token_response_data,
            response_template=self._get_value(auth_endpoint_config, "response_template")
        )

        print("TOKEN EXTERNO OBTENIDO CORRECTAMENTE")

        return token

    def _get_current_user_email(self, current_user: dict):
        if current_user is None:
            return None

        if isinstance(current_user, dict):
            if current_user.get("email"):
                return current_user.get("email")

            payload = current_user.get("payload")

            if isinstance(payload, dict) and payload.get("email"):
                return payload.get("email")

            user = current_user.get("user")

            if user is not None:
                for attr in ["email", "mail", "correo"]:
                    value = getattr(user, attr, None)

                    if value:
                        return value

        for attr in ["email", "mail", "correo"]:
            value = getattr(current_user, attr, None)

            if value:
                return value

        return None

    def _get_token_field_from_response_template(self, response_template):
        if not response_template:
            int_error("EXTERNAL_AUTH_RESPONSE_TEMPLATE_EMPTY", status.HTTP_400_BAD_REQUEST)

        template = response_template

        if isinstance(template, str):
            try:
                template = json.loads(template)
            except ValueError:
                int_error("EXTERNAL_AUTH_RESPONSE_TEMPLATE_INVALID", status.HTTP_400_BAD_REQUEST)

        fields_expected = template.get("fields_expected", {})

        for external_field_name, config in fields_expected.items():
            if not isinstance(config, dict):
                continue

            if config.get("af_field") == "access_token":
                return external_field_name

        int_error("EXTERNAL_AUTH_TOKEN_FIELD_NOT_CONFIGURED", status.HTTP_400_BAD_REQUEST)

    def _extract_token_from_external_response(
        self,
        token_response_data: dict,
        response_template
    ):
        token_field_name = self._get_token_field_from_response_template(
            response_template
        )

        token = token_response_data.get(token_field_name)

        if not token:
            int_error("EXTERNAL_AUTH_TOKEN_NOT_FOUND", status.HTTP_502_BAD_GATEWAY)

        return token

    def _normalize_http_method(self, method_value) -> str:
        if not method_value:
            int_error("EXTERNAL_AUTH_METHOD_NOT_FOUND", status.HTTP_400_BAD_REQUEST)

        raw_method = str(method_value).strip().upper()

        allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]

        if raw_method in allowed_methods:
            return raw_method

        for method in allowed_methods:
            if method in raw_method:
                return method

        int_error("EXTERNAL_AUTH_METHOD_INVALID", status.HTTP_400_BAD_REQUEST)

    def _is_truthy(self, value) -> bool:
        if isinstance(value, bool):
            return value

        if value is None:
            return False

        return str(value).strip().lower() in ["true", "1", "yes", "y", "si", "sí"]

    def _register_external_accounting_error(
        self,
        db: Session,
        payload: AccountingConsultRequest,
        payload_excerpt: dict
    ):
        try:
            self.repo.create_external_accounting_error_log(
                db=db,
                source_system_id=payload.external_project_id,
                payload_excerpt=payload_excerpt
            )
        except Exception as ex:
            print("==============================================")
            print("ERROR NO CONTROLADO REGISTRANDO LOG EXTERNO")
            print("ERROR:", type(ex).__name__)
            print("DETALLE:", str(ex))
            print("==============================================")

    def _raise_external_accounting_consult_error(
        self,
        db: Session,
        payload: AccountingConsultRequest,
        payload_excerpt: dict
    ):
        self._register_external_accounting_error(
            db=db,
            payload=payload,
            payload_excerpt=payload_excerpt
        )

        int_error("EXT_ACCOUNTING_INFO", status.HTTP_502_BAD_GATEWAY)

    def _get_external_response_payload_excerpt(self, response) -> dict:
        status_code = "N/A"
        data = "N/A"

        if response is not None:
            status_code = response.status_code

            try:
                data = response.json()
            except ValueError:
                data = response.text if response.text else "N/A"

        return {
            "status": status_code,
            "data": data
        }

    def _log_accounting_info_consult_audit(
        self,
        db: Session,
        current_user: dict,
        payload: AccountingConsultRequest,
        outcome: str,
        ip: str = None,
        user_agent: str = None
    ):
        try:
            project = self._get_audit_project(db)

            if project is None:
                print("==============================================")
                print("NO SE ENCONTRÓ PROYECTO DE AUDITORÍA")
                print("CODE: AGROFUSION")
                print("==============================================")
                return

            project_id = self._get_value(
                project,
                "af_project_id",
                "project_id",
                "id"
            )

            actor_id = self._get_actor_id(current_user)

            self.audit_repo.log_event(
                db=db,
                action_code="ACCOUNTING_INFO_CONSULT",
                outcome=outcome,
                module_code="ACCOUNTING_VOUCHERS",
                project_id=project_id,
                actor_id=actor_id,
                ip=ip,
                user_agent=user_agent,
                metadata={
                    "external_project": payload.external_project_id
                },
            )

            print("==============================================")
            print("AUDITORÍA CONSULTA CONTABLE REGISTRADA")
            print("ACTION_CODE: ACCOUNTING_INFO_CONSULT")
            print("OUTCOME:", outcome)
            print("PROJECT_ID:", project_id)
            print("EXTERNAL_PROJECT:", payload.external_project_id)
            print("ACTOR_ID:", actor_id)
            print("IP:", ip)
            print("USER_AGENT:", user_agent)
            print("==============================================")

        except Exception as ex:
            print("==============================================")
            print("ERROR REGISTRANDO AUDITORÍA CONSULTA CONTABLE")
            print("ERROR:", type(ex).__name__)
            print("DETALLE:", str(ex))
            print("OUTCOME:", outcome)
            print("EXTERNAL_PROJECT:", payload.external_project_id if payload else None)
            print("==============================================")

    def _log_accounting_transfer_audit(
        self,
        db: Session,
        current_user: dict,
        payload: AccountingTransferRequest,
        outcome: str,
        ip: str = None,
        user_agent: str = None
    ):
        try:
            project = self._get_audit_project(db)

            if project is None:
                print("==============================================")
                print("NO SE ENCONTRÓ PROYECTO DE AUDITORÍA")
                print("CODE: AGROFUSION")
                print("==============================================")
                return

            project_id = self._get_value(
                project,
                "af_project_id",
                "project_id",
                "id"
            )

            actor_id = self._get_actor_id(current_user)

            self.audit_repo.log_event(
                db=db,
                action_code="ACCOUNTING_TRANSFERS",
                outcome=outcome,
                module_code="ACCOUNTING_VOUCHERS",
                project_id=project_id,
                actor_id=actor_id,
                ip=ip,
                user_agent=user_agent,
                metadata={
                    "external_project": payload.external_project_id
                },
            )

            print("==============================================")
            print("AUDITORÍA TRANSFERENCIA CONTABLE REGISTRADA")
            print("ACTION_CODE: ACCOUNTING_TRANSFERS")
            print("OUTCOME:", outcome)
            print("PROJECT_ID:", project_id)
            print("EXTERNAL_PROJECT:", payload.external_project_id)
            print("ACTOR_ID:", actor_id)
            print("IP:", ip)
            print("USER_AGENT:", user_agent)
            print("==============================================")

        except Exception as ex:
            print("==============================================")
            print("ERROR REGISTRANDO AUDITORÍA TRANSFERENCIA CONTABLE")
            print("ERROR:", type(ex).__name__)
            print("DETALLE:", str(ex))
            print("OUTCOME:", outcome)
            print("EXTERNAL_PROJECT:", payload.external_project_id if payload else None)
            print("==============================================")

    def _get_audit_project(self, db: Session):
        if hasattr(self.audit_repo, "get_project_by_code"):
            return self.audit_repo.get_project_by_code(
                db,
                code="AGROFUSION"
            )

        if hasattr(self.audit_repo, "get_project"):
            return self.audit_repo.get_project(
                db,
                code="AGROFUSION"
            )

        if hasattr(self.audit_repo, "get_af_project_by_code"):
            return self.audit_repo.get_af_project_by_code(
                db,
                code="AGROFUSION"
            )

        raise AttributeError(
            "AuditRepository debe tener un método para obtener el proyecto por code='AGROFUSION'."
        )

    def _get_actor_id(self, current_user: dict):
        if current_user is None:
            return None

        if isinstance(current_user, dict):
            user = current_user.get("user")

            if user is not None and hasattr(user, "user_id"):
                return user.user_id

            if current_user.get("user_id"):
                return current_user.get("user_id")

            if current_user.get("sub"):
                return current_user.get("sub")

            payload = current_user.get("payload")

            if isinstance(payload, dict) and payload.get("sub"):
                return payload.get("sub")

        if hasattr(current_user, "user_id"):
            return current_user.user_id

        return None

    def _get_value(self, source, *names):
        if source is None:
            return None

        mapping = getattr(source, "_mapping", None)

        for name in names:
            if isinstance(source, dict) and name in source:
                return source.get(name)

            if mapping is not None and name in mapping:
                return mapping[name]

            if hasattr(source, name):
                return getattr(source, name)

            try:
                return source[name]
            except Exception:
                pass

        return None