FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY /app /app/app
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY scripts /app/scripts

# Default to API server
EXPOSE 8080

# Default command (can be overridden in fly.toml)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--forwarded-allow-ips=*"]