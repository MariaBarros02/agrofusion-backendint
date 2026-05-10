"""
app/scheduler/accounting_retry.py

Job que corre cada 10 minutos y reenvía a contabilidad los lotes
que llevan más de 30 minutos en estado 'processing' sin recibir ACK.

Límite de reintentos: 3 (respeta max_attempts de af_accounting_queue).
"""

import json
import httpx

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import SessionLocal


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────────────────────────────────────

def _get_transfers_pending_retry(db: Session) -> list:
    """
    Devuelve los transfers en 'processing' que:
      - Tienen más de 30 minutos desde sent_at
      - No han superado max_attempts en af_accounting_queue
    """
    cutoff = datetime.utcnow() - timedelta(minutes=30)

    query = text("""
        SELECT
            t.transfer_id,
            t.queue_id,
            t.payload_json,
            t.accounting_entry_id,
            t.external_endpoint_id,
            q.attempts,
            q.max_attempts,
            q.source_project_id
        FROM public.af_accounting_transfers t
        JOIN public.af_accounting_queue q ON q.queue_id = t.queue_id
        WHERE
            t.transfer_status = 'processing'
            AND t.sent_at     < :cutoff
            AND q.attempts    < q.max_attempts
    """)

    rows = db.execute(query, {"cutoff": cutoff}).fetchall()
    return rows


def _get_transfer_endpoint(db: Session, source_project_id: str) -> dict | None:
    """
    Obtiene la configuración del endpoint de contabilidad para el proyecto.
    Reutiliza la misma tabla que ya usa transfer_accounting_batch.
    """
    query = text("""
        SELECT
            e.endpoint_id,
            e.url,
            e.params_template,
            e.body_template,
            e.response_template,
            ct.term_value AS http_method
        FROM public.af_external_endpoints e
        LEFT JOIN public.af_cat_terms ct ON ct.term_id = e.method_term_id
        WHERE e.source_project_id = CAST(:project_id AS uuid)
          AND e.is_active = true
        LIMIT 1
    """)

    row = db.execute(query, {"project_id": source_project_id}).fetchone()
    return dict(row._mapping) if row else None


def _build_api_key_headers(api_key_template: str | None) -> dict:
    """
    Construye los headers de autenticación a partir del template guardado.
    Misma lógica que _build_accounting_transfer_api_key_headers del service.
    """
    if not api_key_template:
        return {}

    try:
        template = json.loads(api_key_template) if isinstance(api_key_template, str) else api_key_template
        return {str(k): str(v) for k, v in template.items()}
    except Exception as ex:
        print(f"[RETRY] Error parseando api_key_template: {ex}")
        return {}


def _increment_attempt(db: Session, queue_id: str, last_error: str | None = None):
    """Incrementa attempts y guarda last_error en af_accounting_queue."""
    query = text("""
        UPDATE public.af_accounting_queue
        SET
            attempts   = attempts + 1,
            last_error = :last_error
        WHERE queue_id = CAST(:queue_id AS uuid)
    """)
    db.execute(query, {"queue_id": queue_id, "last_error": last_error})


def _mark_transfer_retried(db: Session, transfer_id: str):
    """Actualiza sent_at para reiniciar el contador de 30 min."""
    query = text("""
        UPDATE public.af_accounting_transfers
        SET sent_at = :now
        WHERE transfer_id = CAST(:transfer_id AS uuid)
    """)
    db.execute(query, {"now": datetime.utcnow(), "transfer_id": transfer_id})


def _mark_transfer_failed(db: Session, transfer_id: str, queue_id: str, error: str):
    """Marca el transfer y la queue como failed cuando se agotan los reintentos."""
    now = datetime.utcnow()

    db.execute(text("""
        UPDATE public.af_accounting_transfers
        SET
            transfer_status = 'failed',
            error_message   = :error
        WHERE transfer_id = CAST(:transfer_id AS uuid)
    """), {"error": error, "transfer_id": transfer_id})

    db.execute(text("""
        UPDATE public.af_accounting_queue
        SET
            status     = 'failed',
            last_error = :error,
            processed_at = :now
        WHERE queue_id = CAST(:queue_id AS uuid)
    """), {"error": error, "queue_id": queue_id, "now": now})


# ─────────────────────────────────────────────────────────────────────────────
# JOB PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def retry_pending_accounting_transfers():
    """
    Job ejecutado por APScheduler cada 10 minutos.

    Por cada transfer sin ACK después de 30 min:
      1. Verifica que no haya superado max_attempts.
      2. Reenvía el payload a contabilidad.
      3. Incrementa attempts en af_accounting_queue.
      4. Actualiza sent_at para reiniciar el contador.
      5. Si falla o se agotaron los intentos → marca como failed.
    """
    # print("=" * 60)
    # print(f"[RETRY JOB] Iniciando @ {datetime.utcnow().isoformat()}")
    # print("=" * 60)

    db: Session = SessionLocal()

    try:
        pending = _get_transfers_pending_retry(db)
        print(f"[RETRY JOB] Transfers pendientes de reintento: {len(pending)}")

        for row in pending:
            transfer_id   = str(row.transfer_id)
            queue_id      = str(row.queue_id)
            payload_json  = row.payload_json
            project_id    = str(row.source_project_id)
            attempt_num   = row.attempts + 1        # el que se va a ejecutar ahora
            max_attempts  = row.max_attempts

            print(f"\n[RETRY JOB] Transfer {transfer_id} — intento {attempt_num}/{max_attempts}")

            # ── Verificar si ya se agotaron los intentos ──────────────
            if attempt_num > max_attempts:
                error_msg = f"Max reintentos ({max_attempts}) alcanzado sin ACK."
                print(f"[RETRY JOB] {error_msg}")
                _mark_transfer_failed(db, transfer_id, queue_id, error_msg)
                db.commit()
                continue

            # ── Obtener configuración del endpoint ────────────────────
            endpoint = _get_transfer_endpoint(db, project_id)

            if not endpoint:
                error_msg = "Endpoint de contabilidad no encontrado para el proyecto."
                ##print(f"[RETRY JOB] {error_msg}")
                _increment_attempt(db, queue_id, error_msg)
                db.commit()
                continue

            url = endpoint.get("url")
            if not url:
                error_msg = "URL del endpoint de contabilidad vacía."
                #print(f"[RETRY JOB] {error_msg}")
                _increment_attempt(db, queue_id, error_msg)
                db.commit()
                continue

            http_method = (endpoint.get("http_method") or "POST").upper()

            api_key_template = (
                endpoint.get("response_template")
                or endpoint.get("params_template")
                or endpoint.get("body_template")
            )
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                **_build_api_key_headers(api_key_template),
            }

            # ── Envío real a contabilidad ─────────────────────────────
            # NOTA: Mientras el servicio esté en modo simulación comenta
            # el bloque httpx y descomenta el bloque simulado de abajo.
            # ─────────────────────────────────────────────────────────

            try:
                response = httpx.request(
                    method=http_method,
                    url=str(url),
                    json=payload_json,
                    headers=headers,
                    timeout=60.0,
                    trust_env=False,
                )

                if response.status_code < 200 or response.status_code >= 300:
                    raise Exception(
                        f"HTTP {response.status_code}: {response.text[:300]}"
                    )

                print(f"[RETRY JOB] Transfer {transfer_id} reenviado OK.")

            # ── BLOQUE SIMULADO (descomentar si el servicio está caído) ──
            # except Exception:
            #     raise
            # try:
            #     print(f"[RETRY JOB] SIMULACIÓN: reenvío OK para {transfer_id}")
            # ─────────────────────────────────────────────────────────

            except httpx.TimeoutException as ex:
                error_msg = f"Timeout en reintento: {str(ex)}"
                print(f"[RETRY JOB] {error_msg}")
                _increment_attempt(db, queue_id, error_msg)
                db.commit()
                continue

            except Exception as ex:
                error_msg = f"Error en reintento: {type(ex).__name__} — {str(ex)}"
                print(f"[RETRY JOB] {error_msg}")
                _increment_attempt(db, queue_id, error_msg)

                # Si con este intento se llega a max_attempts → failed
                if attempt_num >= max_attempts:
                    _mark_transfer_failed(db, transfer_id, queue_id, error_msg)

                db.commit()
                continue

            # ── Reintento exitoso: actualizar contadores ───────────────
            _increment_attempt(db, queue_id, last_error=None)
            _mark_transfer_retried(db, transfer_id)
            db.commit()

        ##print(f"\n[RETRY JOB] Finalizado @ {datetime.utcnow().isoformat()}")
        ##print("=" * 60)

    except Exception as ex:
        print(f"[RETRY JOB] ERROR GENERAL: {type(ex).__name__} — {str(ex)}")
        db.rollback()

    finally:
        db.close()