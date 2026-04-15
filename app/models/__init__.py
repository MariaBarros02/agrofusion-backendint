"""
Inicializa y registra todos los modelos ORM del proyecto.

Este archivo permite que SQLAlchemy y Alembic detecten
correctamente los modelos al importar el paquete `app.models`.
"""

from app.models.users import Users
from app.models.af_error_log import AfErrorLog
from app.models.cat_terms import CatTerm
from app.models.cat_vocabularies import CatVocabulary
from app.models.af_external_projects import AfExternalProject
from app.models.af_audit_log import AuditLog
from app.models.af_projects import Project
from app.models.af_auth_sessions import AuthSession
from app.models.af_auth_tokens import AuthToken
from app.models.af_modules import AfModule
from app.models.af_projects import Project
from app.models.af_submodules import AfSubmodule
from app.models.af_permissions import AfPermission
from app.models.af_roles_permissions import AfRolePermission 
from app.models.af_roles import AfRole
from app.models.af_user_project_roles import AfUserProjectRole
from app.models.af_accounting_queue import AfAccountingQueue
from app.models.af_accounting_transfers import AfAccountingTransfer
