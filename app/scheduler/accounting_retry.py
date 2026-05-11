"""
app/scheduler/accounting_retry.py

Job que corre cada minuto y gestiona reintentos de lotes contables sin ACK.

FLUJO POR REINTENTO:
  1. Busca transfers en 'processing' con sent_at > 30 min y retry_count < MAX_RETRIES
  2. Obtiene el endpoint igual que transfer_accounting_batch (método + api key)
  3. Si el envío es exitoso:
       - Incrementa af_accounting_transfers.retry_count
       - Crea un nuevo registro en af_accounting_queue
       - Actualiza af_accounting_transfers.queue_id al nuevo queue
       - Actualiza af_accounting_transfers.sent_at (reinicia el contador de 30 min)
  4. Si el envío falla o se agotaron los reintentos:
       - Marca af_accounting_transfers.transfer_status = 'failed'
       - Marca TODAS las af_accounting_queue vinculadas como 'failed'
       - Marca todos los af_audit_receipts del transfer como 'failed'
"""

import json
import httpx

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import SessionLocal
from app.repositories.audit_repository import AuditRepository

_audit_repo = AuditRepository()

MAX_RETRIES     = 3
TIMEOUT_MINUTES = 30


# ─────────────────────────────────────────────────────────────────────────────
# RESOLUCIÓN DE ENDPOINT  (replica la lógica del service original)
# ─────────────────────────────────────────────────────────────────────────────

def _get_transfer_endpoint(db: Session, external_project_id: str) -> dict | None:
    """
    Misma query que checks_repository.get_accounting_transfer_endpoint.
    Devuelve un dict con todas las columnas del endpoint, incluida 'url' ya armada.
    """
    query = text("""
        SELECT
            endpoint.external_endpoint_id,
            endpoint.external_url_id,
            endpoint.external_request_id,
            endpoint.endpoint_name,
            endpoint.path,
            endpoint.method_term_id,
            endpoint.description,
            endpoint.body_template,
            endpoint.body_type,
            endpoint.params_template,
            endpoint.params_type,
            endpoint.response_template,
            endpoint.response_type,
            endpoint.status_term_id,
            endpoint.is_active,
            endpoint.is_protected,

            external_url.external_project_id,
            external_url.client_url,
            external_url.base_url,

            CASE
                WHEN endpoint.external_url_id IS NULL
                     AND (
                         LOWER(endpoint.path) LIKE 'http://%%'
                         OR LOWER(endpoint.path) LIKE 'https://%%'
                     )
                THEN endpoint.path

                WHEN external_url.external_url_id IS NOT NULL
                THEN CONCAT(
                    RTRIM(external_url.client_url, '/'),
                    '/',
                    TRIM(BOTH '/' FROM COALESCE(external_url.base_url, '')),
                    '/',
                    LTRIM(endpoint.path, '/')
                )

                ELSE endpoint.path
            END AS url

        FROM public.af_external_endpoint endpoint
        LEFT JOIN public.af_external_url external_url
            ON external_url.external_url_id = endpoint.external_url_id

        WHERE endpoint.external_request_id = '32ea70a2-cf93-4408-933c-bd2a41aa2744'
          AND endpoint.is_active  = TRUE
          AND endpoint.deleted_at IS NULL
          AND (
              (
                  endpoint.external_url_id IS NOT NULL
                  AND external_url.external_project_id = CAST(:external_project_id AS uuid)
              )
              OR
              (
                  endpoint.external_url_id IS NULL
                  AND (
                      LOWER(endpoint.path) LIKE 'http://%%'
                      OR LOWER(endpoint.path) LIKE 'https://%%'
                  )
              )
          )

        ORDER BY
            CASE WHEN endpoint.external_url_id IS NOT NULL THEN 0 ELSE 1 END,
            endpoint.updated_at DESC NULLS LAST,
            endpoint.created_at DESC NULLS LAST

        LIMIT 1
    """)

    row = db.execute(query, {"external_project_id": external_project_id}).mappings().first()
    return dict(row) if row else None


def _get_cat_term_value(db: Session, term_id: str) -> str | None:
    """
    Replica checks_repository.get_cat_term_value.
    Detecta dinámicamente las columnas de cat_terms y devuelve el valor del método HTTP.
    """
    columns = set(db.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'cat_terms'
    """)).scalars().all())

    id_column    = next((c for c in ["term_id", "cat_term_id", "id"]                                          if c in columns), None)
    value_column = next((c for c in ["code", "term_code", "value", "term_value", "name", "term_name", "description"] if c in columns), None)

    if not id_column or not value_column:
        print(f"[RETRY] No se pudo resolver estructura de cat_terms. columns={columns}")
        return None

    row = db.execute(
        text(f'SELECT "{value_column}" AS value FROM public.cat_terms WHERE "{id_column}" = CAST(:term_id AS uuid) LIMIT 1'),
        {"term_id": term_id}
    ).mappings().first()

    return row.get("value") if row else None


def _normalize_http_method(method_value: str | None) -> str:
    """Replica checks_service._normalize_http_method. Devuelve POST si no resuelve."""
    if not method_value:
        return "POST"

    raw     = str(method_value).strip().upper()
    allowed = ["GET", "POST", "PUT", "PATCH", "DELETE"]

    if raw in allowed:
        return raw

    return next((m for m in allowed if m in raw), "POST")


def _build_api_key_headers(response_template) -> dict:
    """
    Replica checks_service._build_accounting_transfer_api_key_headers.
    No lanza excepción — el scheduler no debe caerse por falta de API key.
    """
    if not response_template:
        print("[RETRY] Sin response_template — enviando sin API key.")
        return {}

    template = response_template
    if isinstance(template, str):
        try:
            template = json.loads(template)
        except ValueError:
            print("[RETRY] response_template no es JSON válido.")
            return {}

    if not isinstance(template, dict):
        return {}

    # Caso 1: dict de headers directo
    headers = template.get("headers")
    if isinstance(headers, dict) and headers:
        return {str(k): str(v) for k, v in headers.items()}

    # Caso 2: header_name + api_key sueltos
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
        print(f"[RETRY] No se encontró API key en template: {template}")
        return {}

    return {str(header_name): str(api_key)}


# ─────────────────────────────────────────────────────────────────────────────
# QUERIES BD
# ─────────────────────────────────────────────────────────────────────────────

def _get_transfers_pending_retry(db: Session) -> list:
    """
    Devuelve transfers en 'processing' con:
      - sent_at hace más de TIMEOUT_MINUTES minutos
      - retry_count < MAX_RETRIES
    """
    cutoff = datetime.utcnow() - timedelta(minutes=TIMEOUT_MINUTES)

    return db.execute(text("""
        SELECT
            t.transfer_id,
            t.queue_id,
            t.payload_json,
            t.accounting_entry_id,
            t.external_endpoint_id,
            t.retry_count,
            t.source_project_id,
            q.source_module_code,
            q.transaction_type,
            q.user_id
        FROM public.af_accounting_transfers t
        JOIN public.af_accounting_queue q ON q.queue_id = t.queue_id
        WHERE
            t.transfer_status = 'processing'
            AND t.sent_at     < :cutoff
            AND COALESCE(t.retry_count, 0) < :max_retries
    """), {"cutoff": cutoff, "max_retries": MAX_RETRIES}).fetchall()


# ─────────────────────────────────────────────────────────────────────────────
# ACCIONES SOBRE BD
# ─────────────────────────────────────────────────────────────────────────────

def _create_new_queue(
    db: Session,
    source_project_id: str,
    source_module_code: str,
    transaction_type: str,
    transaction_data: dict,
    user_id: str,
    retry_count: int,
) -> str:
    """Crea un nuevo af_accounting_queue para el reintento y devuelve su queue_id."""
    transaction_data_text = json.dumps(
        transaction_data if isinstance(transaction_data, dict) else dict(transaction_data),
        ensure_ascii=False,
        default=str,
    )

    new_queue_id = db.execute(text("""
        INSERT INTO public.af_accounting_queue (
            source_project_id, source_module_code, transaction_type,
            transaction_data, accounting_date, user_id,
            status, priority, attempts, max_attempts,
            last_error, created_at, processed_at, sent_at, external_transaction_id
        )
        VALUES (
            CAST(:source_project_id AS uuid),
            :source_module_code,
            :transaction_type,
            CAST(:transaction_data AS jsonb),
            NOW(),
            CAST(:user_id AS uuid),
            'sent', 1, 1, :max_attempts,
            NULL, NOW(), NULL, NOW(), NULL
        )
        RETURNING queue_id
    """), {
        "source_project_id": source_project_id,
        "source_module_code": source_module_code,
        "transaction_type":   transaction_type,
        "transaction_data":   transaction_data_text,
        "user_id":            user_id,
        "max_attempts":       MAX_RETRIES,
    }).scalar()

    print(f"[RETRY] Nueva queue: {new_queue_id} (reintento #{retry_count})")
    return str(new_queue_id)


def _update_transfer_after_retry(db: Session, transfer_id: str, new_queue_id: str):
    """retry_count += 1 · queue_id = nueva queue · sent_at = now()"""
    db.execute(text("""
        UPDATE public.af_accounting_transfers
        SET
            retry_count = COALESCE(retry_count, 0) + 1,
            queue_id    = CAST(:new_queue_id AS uuid),
            sent_at     = :now
        WHERE transfer_id = CAST(:transfer_id AS uuid)
    """), {"new_queue_id": new_queue_id, "now": datetime.utcnow(), "transfer_id": transfer_id})


def _mark_all_failed(db: Session, transfer_id: str, queue_id: str, error: str):
    """
    Marca failed en las 3 tablas.
    En af_accounting_queue marca tanto la queue pasada como
    la que apunta actualmente el transfer (pueden diferir tras reintentos).
    """
    now             = datetime.utcnow()
    error_truncated = error[:1000]

    db.execute(text("""
        UPDATE public.af_accounting_transfers
        SET transfer_status = 'failed',
            error_message   = :error
        WHERE transfer_id = CAST(:transfer_id AS uuid)
    """), {"error": error_truncated, "transfer_id": transfer_id})

    db.execute(text("""
        UPDATE public.af_accounting_queue
        SET status       = 'failed',
            last_error   = :error,
            processed_at = :now
        WHERE queue_id IN (
            CAST(:queue_id AS uuid),
            (SELECT queue_id FROM public.af_accounting_transfers
             WHERE transfer_id = CAST(:transfer_id AS uuid))
        )
    """), {"error": error_truncated, "queue_id": queue_id, "now": now, "transfer_id": transfer_id})

    db.execute(text("""
        UPDATE public.af_audit_receipts
        SET status    = 'failed',
            failed_at = :now,
            error_log = :error
        WHERE accounting_transfer_id = CAST(:transfer_id AS uuid)
          AND status = 'processing'
    """), {"now": now, "error": error_truncated, "transfer_id": transfer_id})

    print(f"[RETRY] Transfer {transfer_id} → FAILED en las 3 tablas.")


# ─────────────────────────────────────────────────────────────────────────────
# AUDITORÍA
# ─────────────────────────────────────────────────────────────────────────────

def _log_retry_audit(
    db: Session,
    transfer_id: str,
    project_id: str,
    outcome: str,       # "success" | "failure"
    retry_number: int,
    actor_id=None,
):
    """
    Registra un evento de auditoría por cada intento de reenvío del scheduler.

    action_code : SENT_RETRY_ACCOUNTING_TRANSFER
    outcome     : success / failure
    metadata    : transfer_id, project_id, retry_number
    """
    try:
        project = _audit_repo.get_project_by_code(db, code="AGROFUSION")

        if project is None:
            print("[RETRY AUDIT] No se encontró proyecto AGROFUSION para auditoría.")
            return

        project_audit_id = getattr(project, "af_project_id", None) or getattr(project, "project_id", None)

        _audit_repo.log_event(
            db=db,
            action_code="SENT_RETRY_ACCOUNTING_TRANSFER",
            outcome=outcome,
            module_code="ACCOUNTING_VOUCHERS",
            project_id=project_audit_id,
            actor_id=actor_id,
            ip=None,
            user_agent="scheduler/accounting_retry",
            metadata={
                "transfer_id":    transfer_id,
                "project_id":     project_id,
                "retry_number":   retry_number,
            },
        )

        print(
            f"[RETRY AUDIT] Auditoría registrada — "
            f"transfer={transfer_id} outcome={outcome} retry_number={retry_number}"
        )

    except Exception as ex:
        # La auditoría nunca debe tumbar el flujo principal
        print(f"[RETRY AUDIT] ERROR registrando auditoría: {type(ex).__name__} — {str(ex)}")


# ─────────────────────────────────────────────────────────────────────────────
# JOB PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def retry_pending_accounting_transfers():
    """
    Job ejecutado por APScheduler cada minuto.

    Por cada transfer sin ACK pasados TIMEOUT_MINUTES:
      - retry_count >= MAX_RETRIES  →  marca failed en las 3 tablas
      - Quedan intentos             →  reenvía con método HTTP + API key correctos
          OK  → nueva queue, actualiza transfer (queue_id, retry_count, sent_at)
          ERR → si era el último intento marca failed; si no, espera próximo ciclo
    """
    print(f"[RETRY JOB] Revisando @ {datetime.utcnow().isoformat()}")

    db: Session = SessionLocal()

    try:
        pending = _get_transfers_pending_retry(db)

        if not pending:
            print("[RETRY JOB] Sin transfers pendientes.")
            return

        print(f"[RETRY JOB] Transfers a procesar: {len(pending)}")

        for row in pending:
            transfer_id        = str(row.transfer_id)
            queue_id           = str(row.queue_id)
            payload_json       = row.payload_json
            project_id         = str(row.source_project_id)
            source_module_code = row.source_module_code
            transaction_type   = row.transaction_type
            user_id            = str(row.user_id) if row.user_id else None
            retry_count        = int(row.retry_count or 0)
            next_retry         = retry_count + 1

            print(f"\n[RETRY JOB] Transfer {transfer_id} — retry {retry_count}/{MAX_RETRIES}")

            # ── ¿Reintentos agotados? ─────────────────────────────────────
            if retry_count >= MAX_RETRIES:
                error_msg = (
                    f"Sin ACK después de {MAX_RETRIES} reintentos "
                    f"({MAX_RETRIES * TIMEOUT_MINUTES} min totales)."
                )
                print(f"[RETRY JOB] {error_msg}")
                _mark_all_failed(db, transfer_id, queue_id, error_msg)
                _log_retry_audit(
                    db=db,
                    transfer_id=transfer_id,
                    project_id=project_id,
                    outcome="failure",
                    retry_number=retry_count,
                )
                db.commit()
                continue

            # ── Validar user_id ───────────────────────────────────────────
            if not user_id or user_id == "None":
                print(f"[RETRY JOB] user_id inválido — transfer {transfer_id}, saltando.")
                db.commit()
                continue

            # ── Obtener endpoint ──────────────────────────────────────────
            endpoint = _get_transfer_endpoint(db, project_id)
            if not endpoint:
                print(f"[RETRY JOB] Endpoint no encontrado para proyecto {project_id}.")
                db.commit()
                continue

            url = endpoint.get("url")
            if not url or (
                not str(url).lower().startswith("http://")
                and not str(url).lower().startswith("https://")
            ):
                print(f"[RETRY JOB] URL inválida: {url}")
                db.commit()
                continue

            # ── Método HTTP (via cat_terms) ────────────────────────────────
            method_term_id = endpoint.get("method_term_id")
            method_value   = _get_cat_term_value(db, str(method_term_id)) if method_term_id else None
            http_method    = _normalize_http_method(method_value)

            # ── API key headers ───────────────────────────────────────────
            api_key_template = (
                endpoint.get("response_template")
                or endpoint.get("params_template")
                or endpoint.get("body_template")
            )
            api_key_headers = _build_api_key_headers(api_key_template)

            headers = {
                "Accept":       "application/json",
                "Content-Type": "application/json",
                **api_key_headers,
            }

            safe_headers = {
                k: ("***" if k.lower() in ("x-api-key", "authorization") else v)
                for k, v in headers.items()
            }
            print(f"[RETRY JOB] URL={url} METHOD={http_method} HEADERS={safe_headers}")

            # ── Envío ─────────────────────────────────────────────────────
            # MODO SIMULACIÓN: comenta el bloque try/except y descomenta
            # las dos líneas del bloque SIMULACIÓN.
            # ─────────────────────────────────────────────────────────────
            send_ok      = False
            send_error   = None
            is_duplicate = False

            try:
                response = httpx.request(
                    method=http_method,
                    url=str(url),
                    json=payload_json,
                    headers=headers,
                    timeout=15.0,
                    trust_env=False,
                )

                if response.status_code == 409:
                    # Contabilidad ya tiene el lote — tratar como envío exitoso
                    is_duplicate = True
                    send_ok      = True
                    print(f"[RETRY JOB] 409 Lote duplicado — contabilidad ya lo tiene. Transfer {transfer_id}")

                elif response.status_code < 200 or response.status_code >= 300:
                    raise Exception(f"HTTP {response.status_code}: {response.text[:300]}")

                else:
                    send_ok = True
                    print(f"[RETRY JOB] Reenvío #{next_retry} OK — transfer {transfer_id}")

            # ── BLOQUE SIMULACIÓN ──────────────────────────────────────────
            # send_ok = True
            # print(f"[RETRY JOB] SIMULACIÓN reenvío #{next_retry} OK — {transfer_id}")
            # ──────────────────────────────────────────────────────────────

            except httpx.TimeoutException as ex:
                send_error = f"Timeout reintento #{next_retry}: {str(ex)}"
                print(f"[RETRY JOB] {send_error}")

            except Exception as ex:
                send_error = f"Error reintento #{next_retry}: {type(ex).__name__} — {str(ex)}"
                print(f"[RETRY JOB] {send_error}")

            # ── Post-envío ────────────────────────────────────────────────
            if send_ok:
                new_queue_id = _create_new_queue(
                    db=db,
                    source_project_id=project_id,
                    source_module_code=source_module_code,
                    transaction_type=transaction_type,
                    transaction_data=payload_json,
                    user_id=user_id,
                    retry_count=next_retry,
                )
                _update_transfer_after_retry(db, transfer_id, new_queue_id)
                _log_retry_audit(
                    db=db,
                    transfer_id=transfer_id,
                    project_id=project_id,
                    outcome="success",
                    retry_number=next_retry,
                )
                if is_duplicate:
                    print(f"[RETRY JOB] Transfer {transfer_id} marcado como reintentado (409 duplicado).")
                else:
                    print(f"[RETRY JOB] retry_count={next_retry}, nueva queue={new_queue_id}")
            else:
                if next_retry >= MAX_RETRIES:
                    _mark_all_failed(db, transfer_id, queue_id, send_error)
                else:
                    print(
                        f"[RETRY JOB] Fallo reintento #{next_retry}. "
                        f"Quedan {MAX_RETRIES - next_retry} intento(s)."
                    )
                _log_retry_audit(
                    db=db,
                    transfer_id=transfer_id,
                    project_id=project_id,
                    outcome="failure",
                    retry_number=next_retry,
                )

            db.commit()

    except Exception as ex:
        print(f"[RETRY JOB] ERROR GENERAL: {type(ex).__name__} — {str(ex)}")
        db.rollback()

    finally:
        db.close()
        print(f"[RETRY JOB] Fin @ {datetime.utcnow().isoformat()}\n")