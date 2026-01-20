FROM python:3.11-slim

WORKDIR /srv

# Install build dependencies for stock-pandas (Rust/Cargo and other tools)
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd -m appuser
RUN chown -R appuser:appuser /srv
USER appuser

CMD ["python", "-m", "app.main"]
