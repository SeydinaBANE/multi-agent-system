#!/bin/sh
set -e

# Wait for PostgreSQL to be reachable before running migrations
python3 -c "
import os, socket, time, sys, urllib.parse

url = os.environ.get('DATABASE_URL', '')
parsed = urllib.parse.urlparse(url.replace('+asyncpg', ''))
host = parsed.hostname or 'localhost'
port = parsed.port or 5432

for attempt in range(30):
    try:
        s = socket.create_connection((host, port), timeout=3)
        s.close()
        print(f'DB {host}:{port} ready.')
        sys.exit(0)
    except Exception as e:
        print(f'Waiting for DB ({attempt+1}/30): {e}')
        time.sleep(3)

print('ERROR: DB not available after 30 attempts')
sys.exit(1)
"

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
