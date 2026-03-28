FROM python:3.11-slim-bookworm

# Install system deps for Playwright + curl_cffi
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libxkbcommon0 libasound2 libpangocairo-1.0-0 \
    libgtk-3-0 libx11-xcb1 fonts-liberation \
    gcc g++ make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install patchright's patched Chromium browser
RUN patchright install chromium --with-deps

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python3", "main.py"]
