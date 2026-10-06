FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn httpx streamlit requests pandas

COPY services/book_service /app/book_service
COPY services/member_service /app/member_service
COPY services/borrow_service /app/borrow_service
COPY services/notification_service /app/notification_service
COPY frontend/app.py /app/frontend/app.py

RUN mkdir -p /app/book_service/data \
    /app/member_service/data \
    /app/borrow_service/data \
    /app/notification_service/data

COPY render-start.sh /app/render-start.sh
RUN chmod +x /app/render-start.sh

EXPOSE 8501

CMD ["/app/render-start.sh"]
