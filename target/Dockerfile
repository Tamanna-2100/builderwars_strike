FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py seed.py ./
EXPOSE 5000
CMD ["sh", "-c", "python seed.py && exec flask --app app run --host=0.0.0.0 --port=5000"]