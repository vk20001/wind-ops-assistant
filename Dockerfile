FROM python:3.12-slim
WORKDIR /agents/wind_ops_assistant
RUN apt-get update && apt-get install -y --no-install-recommends curl nginx \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x /agents/wind_ops_assistant/start.sh
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/agents/wind_ops_assistant
ENV PORT=8080
EXPOSE 8080
CMD ["/agents/wind_ops_assistant/start.sh"]
