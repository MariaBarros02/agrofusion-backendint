"""
Punto de entrada principal de la aplicación FastAPI.

Inicializa la aplicación, configura middlewares globales
y registra los routers de la API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routes.integration import router as router_integration

app = FastAPI(
    root_path="/agrofusion/int",
    title="API Inmero - Backend Integración Agrofusion",
    version="1.0.0",
    description="API de integración para el backend de Agrofusion, encargada de la transferencia de datos entre sistemas."
)
# Orígenes permitidos para solicitudes CORS (frontend)
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]
# Middleware CORS para permitir comunicación entre frontend y backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Registro de rutas relacionadas con integración
app.include_router(router_integration)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=9001,
        reload=True
    )
