# WOOK'S CODING - Django 웹 서비스 (Gunicorn)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# 실제 migrate/collectstatic/gunicorn 기동은 docker-compose command에서 수행
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
