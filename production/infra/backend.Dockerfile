FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ARG SERVICE
COPY services/common /app/common
COPY services/${SERVICE} /app/${SERVICE}
COPY infra/start.sh /app/start.sh
RUN adduser --disabled-password --gecos '' app && chmod +x /app/start.sh
USER app
ENTRYPOINT ["/app/start.sh"]
