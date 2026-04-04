FROM python:3.13-slim

# System deps for WeasyPrint, psycopg2, Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create upload dirs
RUN mkdir -p static/uploads/products/images \
             static/uploads/products/videos \
             static/uploads/products/files \
             static/uploads/invoices

EXPOSE 7777

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7777"]
