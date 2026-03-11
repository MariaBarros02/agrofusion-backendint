# 1. Imagen base oficial de Python
FROM python:3.11-slim

# 2. Directorio de trabajo
WORKDIR /app

# 3. Copiar dependencias
COPY requirements.txt .

# 4. Instalar librerías
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar el código fuente
COPY . .

# 6. Exponer el puerto de Integración
EXPOSE 9001

# 7. Comando de arranque en el puerto 9001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9001"]