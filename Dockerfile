FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py wsgi.py finance.py menu_images.py auto_images.py inventory.py ./
COPY menu-*.jpg drink-*.jpg ./
COPY starter_catalog.py starter_catalog.json ./
COPY index.html app.js finance.js inventory.js accounts.js style.css ./
ENV APP_ENV=production
CMD ["sh", "-c", "gunicorn --workers 1 --bind 0.0.0.0:${PORT:-8000} wsgi:app"]



