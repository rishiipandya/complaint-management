import json
import os
import socket
from datetime import datetime, timezone

import psycopg2

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Notification Service")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5433")),
    "database": os.getenv("DB_NAME", "complaint_management"),
    "user": os.getenv("DB_USER", "complaint_app"),
    "password": os.getenv("DB_PASSWORD", "complaint123")
}

LOGSTASH_HOST = os.getenv("LOGSTASH_HOST")
LOGSTASH_PORT = int(os.getenv("LOGSTASH_PORT", "5000"))


def send_log(level, message):
    log_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "notification-service",
        "level": level,
        "message": message,
        "host": socket.gethostname()
    }

    if not LOGSTASH_HOST:
        print(json.dumps(log_data))
        return

    try:
        with socket.create_connection(
            (LOGSTASH_HOST, LOGSTASH_PORT),
            timeout=1
        ) as connection:
            connection.sendall(
                (json.dumps(log_data) + "\n").encode()
            )
    except Exception:
        print(json.dumps(log_data))


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


class NotificationRequest(BaseModel):
    user_email: str
    message: str


@app.get("/")
def root():
    send_log("INFO", "Notification service root endpoint accessed")
    return {"message": "Notification Service is running"}


@app.get("/health")
def health():
    send_log("INFO", "Notification service health check")
    return {"status": "healthy"}


@app.post("/notifications")
def create_notification(
    notification: NotificationRequest
):
    send_log(
        "INFO",
        f"Creating notification for {notification.user_email}"
    )

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO notifications (user_email, message)
            VALUES (%s, %s)
            RETURNING id, user_email, message
            """,
            (
                notification.user_email,
                notification.message
            )
        )

        row = cursor.fetchone()
        connection.commit()

        send_log(
            "INFO",
            f"Notification created: {row[0]}"
        )

        return {
            "message": "Notification created",
            "notification": {
                "id": row[0],
                "user_email": row[1],
                "message": row[2]
            }
        }

    finally:
        cursor.close()
        connection.close()


@app.get("/notifications")
def get_notifications():
    send_log("INFO", "Fetching notifications")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT id, user_email, message
            FROM notifications
            ORDER BY id
            """
        )

        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "user_email": row[1],
                "message": row[2]
            }
            for row in rows
        ]

    finally:
        cursor.close()
        connection.close()