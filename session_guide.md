docker run -it --rm \
  -v "$PWD/data:/data" \
  python:3.11-slim bash -lc '
    pip install --no-cache-dir telethon && \
    python -c "from telethon import TelegramClient; \
API_ID=1362031; API_HASH=\"3ebd7ce29b3471b585ac9701b55bfdbd\"; \
client=TelegramClient(\"/data/tg\", API_ID, API_HASH); \
client.start(); \
print(\"✅ Session created: /data/tg.session\"); \
client.disconnect()"
  '
