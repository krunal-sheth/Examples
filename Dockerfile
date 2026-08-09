FROM python:3.12-slim
WORKDIR /app
COPY . .
ENV PORT=8000 DATABASE_PATH=/data/jyotish.db PYTHONUNBUFFERED=1
RUN mkdir -p /data && useradd --create-home app && chown -R app:app /app /data
USER app
EXPOSE 8000
CMD ["python3", "server.py"]
