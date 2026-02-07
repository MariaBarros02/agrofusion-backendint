from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session      
from app.core.database import get_db

router = APIRouter(prefix="/integration", tags=["Integración"])
