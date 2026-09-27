import os

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


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


class NotificationRequest(BaseModel):
    user_email: str
    message: str


@app.get("/")
def root():
    return {"message": "Notification Service is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/notifications")
def create_notification(notification: NotificationRequest):
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