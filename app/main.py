"""
app/main.py

Punto de entrada principal de la aplicación FastAPI.

Inicializa la aplicación, configura middlewares globales,
registra los routers de la API y arranca el scheduler de
reintentos contables.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn

from app.routes.integration import router as router_integration
from app.routes.checks import router as router_checks
from app.scheduler.accounting_retry import retry_pending_accounting_transfers


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ciclo de vida de la aplicación:
      - startup : arranca el scheduler de reintentos
      - shutdown: detiene el scheduler limpiamente
    """
    # ── Startup ───────────────────────────────────────────────────────────
    scheduler.add_job(
        retry_pending_accounting_transfers,
        trigger="interval",
        minutes=1,                          # revisa cada 1 min
        id="accounting_retry",
        replace_existing=True,
        max_instances=1,                     # nunca corre en paralelo
    )
    scheduler.start()
    print("[SCHEDULER] Scheduler de reintentos contables iniciado.")
    print("[SCHEDULER] Job: cada 1 min · reintenta transfers sin ACK > 30 min.")

    yield  # ← la app corre aquí

    # ── Shutdown ──────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    print("[SCHEDULER] Scheduler detenido.")


# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="API Inmero - Backend Integración Agrofusion",
    version="1.0.0",
    description=(
        "API de integración para el backend de Agrofusion, "
        "encargada de la transferencia de datos entre sistemas."
    ),
    lifespan=lifespan,
)

# Orígenes permitidos para solicitudes CORS (frontend)
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_integration)
app.include_router(router_checks)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=9001,
        reload=True,        # ⚠️ ver nota abajo
    )