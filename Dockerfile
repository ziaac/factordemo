# FACTOR demo — containerized Streamlit app.
# Build for the linux/amd64 judging VM:
#   docker buildx build --platform linux/amd64 -t <registry>/factor-demo:latest --push .
# Run:
#   docker run -p 8501:8501 \
#     -e AMD_BASE_URL=http://<mi300x-host>:8000/v1 \
#     -e AMD_MODEL=qwen2.5-7b-instruct \
#     -e AMD_API_KEY=... \
#     <registry>/factor-demo:latest
FROM python:3.12-slim

WORKDIR /app

# Only streamlit + anthropic + stdlib are needed; the AMD engine uses urllib.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
