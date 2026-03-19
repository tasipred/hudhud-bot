FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything else
COPY . .

# Railway provides PORT env variable
ENV PORT=8000

# Use shell form to ensure output
CMD python -u main.py
