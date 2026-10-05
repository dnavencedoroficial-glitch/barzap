FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py wsgi.py ./
COPY index.html app.js style.css ./
ENV APP_ENV=production
CMD ["sh", "-c", "gunicorn --workers 1 --bind 0.0.0.0:${PORT:-8000} wsgi:app"]


