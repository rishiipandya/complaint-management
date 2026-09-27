import json
import os
import socket
from datetime import datetime, timezone

import psycopg2

from fastapi import FastAPI, HTTPException

app = FastAPI(title="User Service")

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
        "service": "user-service",
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


@app.get("/")
def root():
    send_log("INFO", "User service root endpoint accessed")
    return {"message": "User Service is running"}


@app.get("/health")
def health():
    send_log("INFO", "User service health check")
    return {"status": "healthy"}


@app.get("/users/{email}")
def get_user(email: str):
    send_log("INFO", f"User lookup: {email}")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT id, name, email, role
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            send_log("WARNING", f"User not found: {email}")

            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        return {
            "id": user[0],
            "name": user[1],
            "email": user[2],
            "role": user[3]
        }

    finally:
        cursor.close()
        connection.close()