FROM python:3.12-slim
WORKDIR /app
COPY check_stock.py .
CMD ["python", "check_stock.py"]
