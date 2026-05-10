import json

from sqlalchemy.orm import Session
from sqlalchemy import cast, String, Numeric, or_, func, text

from app.models.af_accounting_transfers import AfAccountingTransfer
from app.models.af_accounting_queue import AfAccountingQueue
from app.models.af_external_projects import AfExternalProject
from app.models.users import Users


class ChecksRepository:
    def get_check_detail(self, db: Session, check_id: str):
        """
        Consulta el detalle de un comprobante contable por su identificador.
        """
        return (
            db.query(
                AfAccountingTransfer.transfer_id.label("id"),
                AfAccountingTransfer.queue_id.label("queue_id"),
                AfAccountingTransfer.source_project_id.label("source_project_id"),
                AfAccountingTransfer.transaction_type.label("transaction_type"),
                AfAccountingTransfer.payload_json.label("payload_json"),
                AfAccountingTransfer.transfer_status.label("state"),
                AfAccountingTransfer.sent_at.label("sent_at"),
                AfAccountingTransfer.acknowledged_at.label("acknowledged_at"),
                AfAccountingTransfer.accounting_entry_id.label("accounting_entry_id"),
                AfAccountingTransfer.response_json.label("response_json"),
                AfAccountingTransfer.error_message.label("error_message"),
                AfAccountingTransfer.retry_count.label("retry_count"),
                AfAccountingQueue.source_module_code.label("source_module_code"),
                AfAccountingQueue.transaction_data.label("transaction_data"),
                AfAccountingQueue.accounting_date.label("accounting_date"),
                AfAccountingQueue.status.label("queue_status"),
                AfAccountingQueue.attempts.label("attempts"),
                AfAccountingQueue.max_attempts.label("max_attempts"),
                AfAccountingQueue.last_error.label("last_error"),
                AfAccountingQueue.created_at.label("issued_at"),
                AfExternalProject.project_name.label("project_name"),
                AfExternalProject.instance_code.label("project_code"),
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
            .filter(cast(AfAccountingTransfer.transfer_id, String) == check_id)
            .first()
        )

    def get_list_checks(self, db: Session, payload):
        query = (
            db.query(
                AfAccountingTransfer.transfer_id.label("id"),
                AfAccountingTransfer.transaction_type.label("transaction_type"),
                AfExternalProject.project_name.label("project_name"),
                AfExternalProject.instance_code.label("project_code"),
                AfAccountingTransfer.transfer_status.label("state"),
                AfAccountingQueue.created_at.label("issued_at"),
                AfAccountingTransfer.accounting_entry_id.label("accounting_entry_id"),
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
                    AfAccountingTransfer.accounting_entry_id.ilike(search),
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

    def get_accounting_consult_endpoint(
        self,
        db: Session,
        external_project_id: str,
        external_endpoint_id: str
    ):
        """
        Obtiene la configuración del endpoint contable de consulta.

        Para información contable se arma:
            af_external_url.client_url + af_external_endpoint.path
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

                CONCAT(
                    RTRIM(external_url.client_url, '/'),					
					RTRIM(external_url.base_url, '/'),
                    '/',
                    LTRIM(endpoint.path, '/')
                ) AS url,

                'GET' AS http_method,

                NULL AS authorization_type,
                NULL AS authorization_value

            FROM public.af_external_endpoint endpoint
            INNER JOIN public.af_external_url external_url
                ON external_url.external_url_id = endpoint.external_url_id

            WHERE endpoint.external_endpoint_id = CAST(:external_endpoint_id AS uuid)
              AND external_url.external_project_id = CAST(:external_project_id AS uuid)
              AND endpoint.is_active = TRUE
              AND endpoint.deleted_at IS NULL
              AND external_url.client_url IS NOT NULL
              AND TRIM(external_url.client_url) <> ''
            LIMIT 1
        """)

        row = (
            db.execute(
                query,
                {
                    "external_project_id": external_project_id,
                    "external_endpoint_id": external_endpoint_id,
                }
            )
            .mappings()
            .first()
        )

        if row:
            print("==============================================")
            print("CONFIGURACIÓN ENDPOINT EXTERNO ENCONTRADA")
            print("EXTERNAL_ENDPOINT_ID:", row.get("external_endpoint_id"))
            print("EXTERNAL_URL_ID:", row.get("external_url_id"))
            print("CLIENT_URL:", row.get("client_url"))
            print("BASE_URL:", row.get("base_url"))
            print("PATH:", row.get("path"))
            print("IS_PROTECTED:", row.get("is_protected"))
            print("URL ARMADA:", row.get("url"))
            print("==============================================")
        else:
            print("==============================================")
            print("NO SE ENCONTRÓ CONFIGURACIÓN ENDPOINT EXTERNO")
            print("EXTERNAL_PROJECT_ID:", external_project_id)
            print("EXTERNAL_ENDPOINT_ID:", external_endpoint_id)
            print("==============================================")

        return row

    def get_accounting_transfer_endpoint(
        self,
        db: Session,
        external_project_id: str
    ):
        """
        Obtiene la configuración del endpoint de contabilidad para transferir lotes.

        Busca:
            af_external_endpoint.external_request_id = 32ea70a2-cf93-4408-933c-bd2a41aa2744

        Soporta dos formas:

        1. Con external_url_id:
            af_external_url.client_url + af_external_url.base_url + af_external_endpoint.path

        2. Sin external_url_id:
            af_external_endpoint.path ya trae la URL completa.
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
              AND endpoint.is_active = TRUE
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
                CASE
                    WHEN endpoint.external_url_id IS NOT NULL THEN 0
                    ELSE 1
                END,
                endpoint.updated_at DESC NULLS LAST,
                endpoint.created_at DESC NULLS LAST

            LIMIT 1
        """)

        row = (
            db.execute(
                query,
                {
                    "external_project_id": external_project_id,
                }
            )
            .mappings()
            .first()
        )

        if row:
            print("==============================================")
            print("CONFIGURACIÓN ENDPOINT CONTABILIDAD ENCONTRADA")
            print("EXTERNAL_ENDPOINT_ID:", row.get("external_endpoint_id"))
            print("EXTERNAL_URL_ID:", row.get("external_url_id"))
            print("EXTERNAL_REQUEST_ID:", row.get("external_request_id"))
            print("ENDPOINT_NAME:", row.get("endpoint_name"))
            print("CLIENT_URL:", row.get("client_url"))
            print("BASE_URL:", row.get("base_url"))
            print("PATH:", row.get("path"))
            print("METHOD_TERM_ID:", row.get("method_term_id"))
            print("RESPONSE_TEMPLATE:", row.get("response_template"))
            print("URL CONTABILIDAD:", row.get("url"))
            print("==============================================")
        else:
            print("==============================================")
            print("NO SE ENCONTRÓ ENDPOINT DE CONTABILIDAD")
            print("EXTERNAL_PROJECT_ID:", external_project_id)
            print("EXTERNAL_REQUEST_ID: 32ea70a2-cf93-4408-933c-bd2a41aa2744")
            print("==============================================")

        return row

    def get_external_service_token_endpoint(
        self,
        db: Session,
        external_project_id: str
    ):
        """
        Obtiene la configuración del endpoint externo para token.

        Busca:
            external_request_id = 04a84c27-807a-45fc-9840-286593cb7dd9

        Arma:
            af_external_url.client_url + af_external_url.base_url + af_external_endpoint.path
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

                CONCAT(
                    RTRIM(external_url.client_url, '/'),
                    '/',
                    TRIM(BOTH '/' FROM COALESCE(external_url.base_url, '')),
                    '/',
                    LTRIM(endpoint.path, '/')
                ) AS url

            FROM public.af_external_endpoint endpoint
            INNER JOIN public.af_external_url external_url
                ON external_url.external_url_id = endpoint.external_url_id

            WHERE endpoint.external_request_id = '04a84c27-807a-45fc-9840-286593cb7dd9'
              AND external_url.external_project_id = CAST(:external_project_id AS uuid)
              AND endpoint.is_active = TRUE
              AND endpoint.deleted_at IS NULL
              AND external_url.client_url IS NOT NULL
              AND TRIM(external_url.client_url) <> ''
            LIMIT 1
        """)

        row = (
            db.execute(
                query,
                {
                    "external_project_id": external_project_id,
                }
            )
            .mappings()
            .first()
        )

        if row:
            print("==============================================")
            print("CONFIGURACIÓN ENDPOINT TOKEN EXTERNO ENCONTRADA")
            print("EXTERNAL_ENDPOINT_ID:", row.get("external_endpoint_id"))
            print("EXTERNAL_URL_ID:", row.get("external_url_id"))
            print("EXTERNAL_REQUEST_ID:", row.get("external_request_id"))
            print("CLIENT_URL:", row.get("client_url"))
            print("BASE_URL:", row.get("base_url"))
            print("PATH:", row.get("path"))
            print("METHOD_TERM_ID:", row.get("method_term_id"))
            print("URL TOKEN:", row.get("url"))
            print("==============================================")
        else:
            print("==============================================")
            print("NO SE ENCONTRÓ ENDPOINT TOKEN EXTERNO")
            print("EXTERNAL_PROJECT_ID:", external_project_id)
            print("==============================================")

        return row

    def get_cat_term_value(
        self,
        db: Session,
        term_id: str
    ):
        """
        Obtiene el valor textual del método HTTP desde cat_terms.

        Se hace defensivo porque no siempre conocemos si la columna se llama:
        term_id, cat_term_id, id, code, name, value, etc.
        """

        columns_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'cat_terms'
        """)

        columns = set(db.execute(columns_query).scalars().all())

        id_candidates = [
            "term_id",
            "cat_term_id",
            "id",
        ]

        value_candidates = [
            "code",
            "term_code",
            "value",
            "term_value",
            "name",
            "term_name",
            "description",
        ]

        id_column = None
        value_column = None

        for candidate in id_candidates:
            if candidate in columns:
                id_column = candidate
                break

        for candidate in value_candidates:
            if candidate in columns:
                value_column = candidate
                break

        if not id_column or not value_column:
            print("==============================================")
            print("NO SE PUDO RESOLVER ESTRUCTURA DE cat_terms")
            print("ID_COLUMN:", id_column)
            print("VALUE_COLUMN:", value_column)
            print("COLUMNS:", columns)
            print("==============================================")
            return None

        query = text(f"""
            SELECT "{value_column}" AS value
            FROM public.cat_terms
            WHERE "{id_column}" = CAST(:term_id AS uuid)
            LIMIT 1
        """)

        row = (
            db.execute(
                query,
                {
                    "term_id": term_id,
                }
            )
            .mappings()
            .first()
        )

        if row:
            print("==============================================")
            print("CAT_TERM ENCONTRADO")
            print("TERM_ID:", term_id)
            print("VALUE:", row.get("value"))
            print("==============================================")
        else:
            print("==============================================")
            print("CAT_TERM NO ENCONTRADO")
            print("TERM_ID:", term_id)
            print("==============================================")

        return row.get("value") if row else None

    def get_overlapping_accounting_transfer_period(
        self,
        db: Session,
        external_project_id: str,
        external_endpoint_id: str,
        since_period: str,
        until_period: str
    ):
        query = text("""
            SELECT
                transfer.transfer_id,
                transfer.source_project_id,
                transfer.transaction_type,
                transfer.transfer_status,
                transfer.sent_at,
                transfer.acknowledged_at,

                transfer.payload_json #>> '{metadata,RequestedPeriod,From}' AS existing_from,
                transfer.payload_json #>> '{metadata,RequestedPeriod,To}' AS existing_to

            FROM public.af_accounting_transfers transfer

              WHERE transfer.source_project_id = CAST(:external_project_id AS uuid)
              AND transfer.external_endpoint_id = CAST(:external_endpoint_id AS uuid)
            
              AND transfer.payload_json #>> '{metadata,RequestedPeriod,From}' IS NOT NULL
              AND transfer.payload_json #>> '{metadata,RequestedPeriod,To}' IS NOT NULL

              AND transfer.payload_json #>> '{metadata,RequestedPeriod,From}' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
              AND transfer.payload_json #>> '{metadata,RequestedPeriod,To}' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'

              AND (transfer.payload_json #>> '{metadata,RequestedPeriod,From}')::date <= CAST(:until_period AS date)
              AND (transfer.payload_json #>> '{metadata,RequestedPeriod,To}')::date >= CAST(:since_period AS date)

            ORDER BY transfer.sent_at DESC NULLS LAST
            LIMIT 1
        """)

        row = (
            db.execute(
                query,
                {
                    "external_project_id": external_project_id,
                    "external_endpoint_id": external_endpoint_id,
                    "since_period": since_period,
                    "until_period": until_period,
                }
            )
            .mappings()
            .first()
        )

        if row:
            print("==============================================")
            print("TRANSFERENCIA CONTABLE CRUZADA ENCONTRADA")
            print("TRANSFER_ID:", row.get("transfer_id"))
            print("SOURCE_PROJECT_ID:", row.get("source_project_id"))
            print("TRANSACTION_TYPE:", row.get("transaction_type"))
            print("TRANSFER_STATUS:", row.get("transfer_status"))
            print("EXISTING_FROM:", row.get("existing_from"))
            print("EXISTING_TO:", row.get("existing_to"))
            print("REQUEST_FROM:", since_period)
            print("REQUEST_TO:", until_period)
            print("==============================================")
        else:
            print("==============================================")
            print("NO EXISTEN TRANSFERENCIAS CRUZADAS PARA EL PERIODO")
            print("SOURCE_PROJECT_ID:", external_project_id)
            print("REQUEST_FROM:", since_period)
            print("REQUEST_TO:", until_period)
            print("==============================================")

        return row

    def create_accounting_transfer(
        self,
        db: Session,
        queue_id: str,
        external_project_id: str,
        external_endpoint_id:str,
        transaction_type: str,
        payload_json: dict,
        accounting_entry_id: str
    ):
        """
        Registra el lote completo enviado a contabilidad en af_accounting_transfers.

        Estado inicial:
            transfer_status = processing
            retry_count = 1
        """

        payload_json_text = json.dumps(
            payload_json,
            ensure_ascii=False,
            default=str
        )

        query = text("""
            INSERT INTO public.af_accounting_transfers (
                queue_id,
                source_project_id,
                transaction_type,
                payload_json,
                transfer_status,
                sent_at,
                acknowledged_at,
                accounting_entry_id,
                response_json,
                error_message,
                retry_count,
                external_endpoint_id
            )
            VALUES (
                CAST(:queue_id AS uuid),
                CAST(:source_project_id AS uuid),
                :transaction_type,
                CAST(:payload_json AS jsonb),
                'processing',
                NOW(),
                NULL,
                :accounting_entry_id,
                NULL,
                NULL,
                1,
                CAST(:external_endpoint_id AS uuid)
            )
            RETURNING transfer_id
        """)

        transfer_id = db.execute(
            query,
            {
                "queue_id": queue_id,
                "source_project_id": external_project_id,
                "external_endpoint_id": external_endpoint_id,
                "transaction_type": transaction_type,
                "payload_json": payload_json_text,
                "accounting_entry_id": accounting_entry_id,
            }
        ).scalar()

        print("==============================================")
        print("LOTE CONTABLE REGISTRADO EN af_accounting_transfers")
        print("TRANSFER_ID:", transfer_id)
        print("SOURCE_PROJECT_ID:", external_project_id)
        print("TRANSACTION_TYPE:", transaction_type)
        print("ACCOUNTING_ENTRY_ID:", accounting_entry_id)
        print("==============================================")

        return transfer_id

    def create_accounting_queue(
        self,
        db: Session,
        source_project_id: str,
        source_module_code: str,
        transaction_type: str,
        transaction_data: dict,
        user_id: str
    ):
        """
        Crea un registro en af_accounting_queue.
        """

        transaction_data_text = json.dumps(
            transaction_data,
            ensure_ascii=False,
            default=str
        )

        query = text("""
            INSERT INTO public.af_accounting_queue (
                source_project_id,
                source_module_code,
                transaction_type,
                transaction_data,
                accounting_date,
                user_id,
                status,
                priority,
                attempts,
                max_attempts,
                last_error,
                created_at,
                processed_at,
                sent_at,
                external_transaction_id
            )
            VALUES (
                CAST(:source_project_id AS uuid),
                :source_module_code,
                :transaction_type,
                CAST(:transaction_data AS jsonb),
                NOW(),
                CAST(:user_id AS uuid),
                'sent',
                1,
                1,
                2,
                NULL,
                NOW(),
                NULL,
                NOW(),
                NULL
            )
            RETURNING queue_id
        """)

        queue_id = db.execute(
            query,
            {
                "source_project_id": source_project_id,
                "source_module_code": source_module_code,
                "transaction_type": transaction_type,
                "transaction_data": transaction_data_text,
                "user_id": user_id
            }
        ).scalar()

        print("==============================================")
        print("QUEUE CONTABLE REGISTRADO")
        print("QUEUE_ID:", queue_id)
        print("SOURCE_PROJECT_ID:", source_project_id)
        print("TRANSACTION_TYPE:", transaction_type)
        print("==============================================")

        return queue_id

    def create_accounting_audit_receipts(
        self,
        db: Session,
        accounting_transfer_id: str,
        accounting_entry_id: str,
        normalized_json: dict
    ):
        """
        Registra cada invoice y cada transaction en af_audit_receipts.

        Por requerimiento:
            status = processing
            idempotency_key = accounting_transfer.accounting_entry_id
            trace_id = 1
            queued_at = now()
            processed_at = now()
            accounting_transfer_id = af_accounting_transfers.transfer_id
        """

        documents = []

        invoices = normalized_json.get("invoices") or []
        transactions = normalized_json.get("transactions") or []

        for invoice in invoices:
            documents.append(invoice)

        for transaction in transactions:
            documents.append(transaction)

        query = text("""
            INSERT INTO public.af_audit_receipts (
                payload,
                status,
                audit_id,
                idempotency_key,
                trace_id,
                queued_at,
                processed_at,
                failed_at,
                error_log,
                created_at,
                accounting_transfer_id
            )
            VALUES (
                CAST(:payload AS jsonb),
                'processing',
                NULL,
                :idempotency_key,
                1,
                NOW(),
                NOW(),
                NULL,
                NULL,
                NOW(),
                CAST(:accounting_transfer_id AS uuid)
            )
        """)

        total_inserted = 0

        for document in documents:
            document_json_text = json.dumps(
                document,
                ensure_ascii=False,
                default=str
            )

            db.execute(
                query,
                {
                    "payload": document_json_text,
                    "idempotency_key": accounting_entry_id,
                    "accounting_transfer_id": accounting_transfer_id,
                }
            )

            total_inserted += 1

        print("==============================================")
        print("DOCUMENTOS REGISTRADOS EN af_audit_receipts")
        print("ACCOUNTING_TRANSFER_ID:", accounting_transfer_id)
        print("TOTAL_DOCUMENTOS:", total_inserted)
        print("==============================================")

        return total_inserted

    def create_external_accounting_error_log(
        self,
        db: Session,
        source_system_id: str,
        payload_excerpt: dict
    ):
        if not payload_excerpt:
            payload_excerpt = {
                "status": "N/A",
                "data": "N/A"
            }

        payload_excerpt_json = json.dumps(
            payload_excerpt,
            ensure_ascii=False,
            default=str
        )

        query = text("""
            INSERT INTO public.af_error_log (
                context_id,
                source_system_id,
                message,
                payload_excerpt,
                severity_id,
                "at",
                error_code,
                component
            )
            VALUES (
                CAST(:context_id AS uuid),
                CAST(:source_system_id AS uuid),
                :message,
                CAST(:payload_excerpt AS jsonb),
                CAST(:severity_id AS uuid),
                NOW(),
                :error_code,
                :component
            )
        """)

        try:
            db.execute(
                query,
                {
                    "context_id": "aa1219ec-27c4-4734-ae4e-01ab2b340e34",
                    "source_system_id": source_system_id,
                    "message": "No se pudo consultar información contable del proyecto externo",
                    "payload_excerpt": payload_excerpt_json,
                    "severity_id": "6a0a37a6-0c63-4d16-8aaa-281cc6dc53fb",
                    "error_code": "EXT_ACCOUNTING_INFO",
                    "component": "Consulta de informacion contable",
                }
            )

            db.commit()

            print("==============================================")
            print("ERROR DE CONSULTA CONTABLE EXTERNA REGISTRADO")
            print("SOURCE_SYSTEM_ID:", source_system_id)
            print("PAYLOAD_EXCERPT:", payload_excerpt_json)
            print("==============================================")

        except Exception as ex:
            db.rollback()

            print("==============================================")
            print("ERROR REGISTRANDO AF_ERROR_LOG")
            print("ERROR:", type(ex).__name__)
            print("DETALLE:", str(ex))
            print("SOURCE_SYSTEM_ID:", source_system_id)
            print("PAYLOAD_EXCERPT:", payload_excerpt_json)
            print("==============================================")

    def get_accounting_transfer_by_exchange_id(
        self,
        db: Session,
        exchange_id: str,
    ):
        """
        Busca un registro en af_accounting_transfers
        por accounting_entry_id = exchangeId recibido en el ACK.
        """

        query = text("""
            SELECT
                transfer_id,
                source_project_id,
                transfer_status,
                accounting_entry_id
            FROM public.af_accounting_transfers
            WHERE accounting_entry_id = :exchange_id
            LIMIT 1
        """)

        result = db.execute(
            query,
            {"exchange_id": exchange_id}
        ).fetchone()

        print("==============================================")
        print("BÚSQUEDA af_accounting_transfers POR EXCHANGE_ID")
        print("EXCHANGE_ID:", exchange_id)
        print("ENCONTRADO:", result is not None)
        print("==============================================")

        return result

    def update_accounting_transfer_ack(
        self,
        db: Session,
        transfer_id: str,
        transfer_status: str,
        acknowledged_at,
        response_json,
        error_message=None,          # solo se usa cuando transfer_status == "failed"
    ):
        response_json_text = (
            json.dumps(response_json, ensure_ascii=False, default=str)
            if response_json is not None
            else None
        )

        # error_message solo en failed; en partial queda NULL
        if transfer_status == "failed":
            error_message_text = response_json_text          # copia del ACK
        else:
            error_message_text = None                        # partial → NULL

        query = text("""
            UPDATE public.af_accounting_transfers
            SET
                transfer_status = :transfer_status,
                acknowledged_at = :acknowledged_at,
                response_json   = CAST(:response_json AS jsonb),
                error_message   = :error_message
            WHERE transfer_id = CAST(:transfer_id AS uuid)
        """)

        db.execute(query, {
            "transfer_status": transfer_status,
            "acknowledged_at": acknowledged_at,
            "response_json":   response_json_text,
            "error_message":   error_message_text,
            "transfer_id":     transfer_id,
        })

    def update_accounting_queue_status(
        self,
        db: Session,
        transfer_id: str,
        queue_status: str,
        processed_at,
    ):
        query = text("""
            UPDATE public.af_accounting_queue q
            SET
                status       = :queue_status,
                processed_at = :processed_at
            FROM public.af_accounting_transfers t
            WHERE t.queue_id   = q.queue_id
            AND t.transfer_id = CAST(:transfer_id AS uuid)
        """)

        result = db.execute(query, {
            "queue_status": queue_status,
            "processed_at": processed_at,
            "transfer_id":  transfer_id,
        })

        print("==============================================")
        print("af_accounting_queue ACTUALIZADO POR ACK")
        print("TRANSFER_ID:",     transfer_id)
        print("STATUS:",          queue_status)
        print("PROCESSED_AT:",    processed_at)
        print("FILAS AFECTADAS:", result.rowcount)
        print("==============================================")
            

    def update_audit_receipts_status(
        self,
        db: Session,
        accounting_transfer_id: str,
        status: str,
    ):
        """
        Actualiza el status de TODOS los af_audit_receipts
        que pertenecen a un af_accounting_transfers.

        Se usa cuando el ACK llega exitoso (status = sent).
        """

        query = text("""
            UPDATE public.af_audit_receipts
            SET status = :status
            WHERE accounting_transfer_id = CAST(:accounting_transfer_id AS uuid)
        """)

        result = db.execute(
            query,
            {
                "status": status,
                "accounting_transfer_id": accounting_transfer_id,
            }
        )

        print("==============================================")
        print("af_audit_receipts ACTUALIZADOS (LOTE COMPLETO)")
        print("ACCOUNTING_TRANSFER_ID:", accounting_transfer_id)
        print("STATUS:", status)
        print("FILAS AFECTADAS:", result.rowcount)
        print("==============================================")
    def update_audit_receipt_sent(
        self,
        db: Session,
        accounting_transfer_id: str,
        document_id: str,
    ):
        query = text("""
            UPDATE public.af_audit_receipts
            SET status = 'sent'
            WHERE
                accounting_transfer_id = :accounting_transfer_id
                AND (
                    payload->>'DocumentId' = :document_id
                    OR payload->'Header'->>'DocumentId' = :document_id
                )
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


    def update_audit_receipt_failed(
        self,
        db: Session,
        accounting_transfer_id: str,
        document_id: str,
        failed_at,
        error_log: dict,
    ):
        error_log_text = json.dumps(error_log, ensure_ascii=False, default=str)

        query = text("""
            UPDATE public.af_audit_receipts
            SET
                status    = 'failed',
                failed_at = :failed_at,
                error_log = :error_log
            WHERE
                accounting_transfer_id = :accounting_transfer_id
                AND (
                    payload->>'DocumentId' = :document_id
                    OR payload->'Header'->>'DocumentId' = :document_id
                )
        """)

        result = db.execute(query, {
            "failed_at":              failed_at,
            "error_log":              error_log_text,
            "accounting_transfer_id": accounting_transfer_id,
            "document_id":            document_id,
        })

        print("==============================================")
        print("af_audit_receipt MARCADO COMO FAILED")
        print("ACCOUNTING_TRANSFER_ID:", accounting_transfer_id)
        print("DOCUMENT_ID:",           document_id)
        print("FAILED_AT:",             failed_at)
        print("ERROR_LOG:",             error_log_text)
        print("FILAS AFECTADAS:",       result.rowcount)
        print("==============================================")