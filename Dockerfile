FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY clientflow /app/clientflow
COPY config /app/config
COPY frontend /app/frontend
ENV DEMO_MODE=mock PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn","clientflow.api:app","--host","0.0.0.0","--port","8000","--workers","1"]
