# ⚙️ Agrofusion – Backend 🌱💧

Repositorio de uno de los **Backends del proyecto Agrofusion**, desarrollado como parte del Proyecto Integrador 4.  
Este servicio expone APIs REST y forma parte de la arquitectura distribuida del sistema.

Backends disponibles:
- 🔐 Authentication
- 💳 Auditory
- 🔧 Integration

---

## 🚀 Tecnologías

- 🐍 Python **3.11** (uso obligatorio)
- ⚡ FastAPI
- 🦄 Uvicorn
- 📦 pip
- 🗄️ Base de datos relacional (configurada vía `.env`)

---

## ✅ Requisitos previos

Antes de ejecutar el backend, asegúrate de contar con:

- 💻 Visual Studio Code
- 🐍 Python **3.11** (no usar otra versión)
- 🐙 Cuenta de GitHub
- 🌐 Conexión a internet estable
- 🚫 VPN desactivada
- 🔌 Puerto disponible según el backend:
  - Authentication → **8000**
  - Auditory → **9000**
  - Integration → **9001**

---

## 📂 Clonar el repositorio

Ejecuta el comando correspondiente según el backend:

```bash
git clone https://github.com/MariaBarros02/agrofusion-backendauth.git
git clone https://github.com/MariaBarros02/agrofusion-backendaudit.git
git clone https://github.com/MariaBarros02/agrofusion-backendint.git
```
Ingresa a la carpeta del backend clonado:

```bash
cd agrofusion-backend[auth|audit|int]
```

## 🔐 Variables de entorno

El backend requiere un archivo env.deployment para funcionar correctamente.

📥 El archivo se encuentra en el Drive del proyecto.

👉 Descarga el archivo correspondiente a Backend (Todos) y colócalo en la raíz del proyecto.

## 🗄️ Base de datos

Antes de ejecutar el backend, asegúrate de tener la base de datos desplegada localmente.

Tutorial:

1.TUTORIAL DESPLIEGUE LOCAL DB [https://docs.google.com/document/d/1QNf-j26LILCnDwDPwbzG_oGjvrJ9CePMxgCaMUUNQfc/edit?usp=drive_link]


Edita el archivo env.deployment y actualiza la variable:

**` DATABASE_URL= `**


Con los valores correctos de:

- host
- puerto
- usuario
- contraseña
- nombre de la base de datos

⚠️ **` Importante: `**

No cambiar el nombre del archivo.

No subir el archivo al repositorio.

## 🧪 Crear entorno virtual

Desde la raíz del proyecto, ejecuta:
```bash
py -3.11 -m venv venv
```

Activa el entorno virtual:
```bash
Windows

venv/Scripts/activate


Linux / Mac

source venv/bin/activate
```
## 📦 Instalación de dependencias

Con el entorno virtual activo, ejecuta:
```bash
pip install -r requirements.txt
``` 

⏳ Este proceso puede tardar algunos minutos.

## ▶️ Ejecutar el backend

Levanta el servicio en el puerto correspondiente:
```bash
uvicorn app.main:app --reload --port [PUERTO]
```

Puertos por backend:

- Authentication → 8000

- Auditory → 9000

- Integration → 9001

⚠️ No cierres esta terminal, o el servicio se detendrá.

## 📖 Swagger – Documentación de la API

Cada backend expone su documentación Swagger en:

- Authentication → http://localhost:8000/docs

- Auditory → http://localhost:9000/docs
 
- Integration → http://localhost:9001/docs

🔒 Algunos endpoints requieren autenticación.
Deberás iniciar sesión y usar el token JWT en los endpoints protegidos.


## 🔗 Integración con otros servicios

Este backend se integra con:

Otros backends de Agrofusion

Frontend Web (agrofusion-frontendweb)

Asegúrate de que todos los servicios estén activos para pruebas completas.

## 🎉 Resultado

El backend estará ejecutándose localmente y listo para recibir solicitudes.
Agrofusion 🌱💧 ya puede comunicarse correctamente entre servicios.


Desarrollado por el equipo Agrofusion 💚
