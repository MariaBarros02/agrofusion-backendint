# 1. Imagen base oficial de Python
FROM python:3.11-slim

# 2. Directorio de trabajo
WORKDIR /app

# 3. Copiar dependencias
COPY requirements.txt .

# Copia los archivos del backend al contenedor
COPY . /app/

# 4. Instalar librerías
RUN pip install --no-cache-dir -r requirements.txt


# 6. Exponer el puerto de Integración
EXPOSE 9109

# 7. Comando de arranque en el puerto 9001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9101"]