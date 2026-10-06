#!/bin/sh

cd /app/book_service
DB_PATH=/app/book_service/data/books.db uvicorn main:app --host 0.0.0.0 --port 8001 &

cd /app/member_service
DB_PATH=/app/member_service/data/members.db uvicorn main:app --host 0.0.0.0 --port 8002 &

cd /app/notification_service
DB_PATH=/app/notification_service/data/notifications.db uvicorn main:app --host 0.0.0.0 --port 8004 &

cd /app/borrow_service
BOOK_SERVICE_URL=http://127.0.0.1:8001 \
MEMBER_SERVICE_URL=http://127.0.0.1:8002 \
NOTIFICATION_SERVICE_URL=http://127.0.0.1:8004 \
DB_PATH=/app/borrow_service/data/borrows.db \
uvicorn main:app --host 0.0.0.0 --port 8003 &

cd /app
streamlit run frontend/app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}"
