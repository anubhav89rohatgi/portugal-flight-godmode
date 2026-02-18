FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir requests python-dotenv streamlit

RUN ls -la

CMD streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0
