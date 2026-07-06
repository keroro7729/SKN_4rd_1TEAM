# WOOK'S CODING - Docker Worker (코드 실행)
# 사용자 코드 실행 언어와 동일하게 Python 3.11 사용
FROM python:3.11-slim

# unshare(네트워크 네임스페이스 격리)용 util-linux
RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
