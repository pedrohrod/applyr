FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# instala os browsers do Playwright
RUN playwright install chromium --with-deps

COPY . .

# volumes externos montados em runtime:
#   /app/resume   → seu currículo PDF
#   /app/data     → banco SQLite + CSV
#   /app/logs     → logs
#   /app/config   → settings.yaml + profile.yaml

CMD ["python", "main.py"]
