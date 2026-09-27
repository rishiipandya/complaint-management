import json
import os
import socket
from datetime import datetime, timezone

import jwt
import psycopg2

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="Complaint Service")

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-later")
ALGORITHM = "HS256"

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
        "service": "complaint-service",
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


def verify_token(authorization: str):
    if not authorization:
        send_log("WARNING", "Missing authorization header")

        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    token = authorization.split(" ")[1]

    try:
        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

    except jwt.InvalidTokenError:
        send_log("WARNING", "Invalid JWT token")

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )


class ComplaintRequest(BaseModel):
    title: str
    description: str
    category: str


class StatusUpdate(BaseModel):
    status: str


@app.get("/")
def root():
    send_log("INFO", "Complaint service root endpoint accessed")
    return {"message": "Complaint Service is running"}


@app.get("/health")
def health():
    send_log("INFO", "Complaint service health check")
    return {"status": "healthy"}


@app.post("/complaints")
def create_complaint(
    complaint: ComplaintRequest,
    authorization: str = Header(None)
):
    user = verify_token(authorization)

    send_log(
        "INFO",
        f"Creating complaint for {user['email']}"
    )

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO complaints
            (title, description, category, user_email, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, title, description, category, user_email, status
            """,
            (
                complaint.title,
                complaint.description,
                complaint.category,
                user["email"],
                "OPEN"
            )
        )

        row = cursor.fetchone()
        connection.commit()

        send_log(
            "INFO",
            f"Complaint created: {row[0]}"
        )

        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "category": row[3],
            "user_email": row[4],
            "status": row[5]
        }

    finally:
        cursor.close()
        connection.close()


@app.get("/complaints")
def get_complaints(
    authorization: str = Header(None)
):
    verify_token(authorization)

    send_log("INFO", "Fetching complaints")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT id, title, description, category, user_email, status
            FROM complaints
            ORDER BY id
            """
        )

        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "category": row[3],
                "user_email": row[4],
                "status": row[5]
            }
            for row in rows
        ]

    finally:
        cursor.close()
        connection.close()


@app.get("/complaints/{complaint_id}")
def get_complaint(
    complaint_id: int,
    authorization: str = Header(None)
):
    verify_token(authorization)

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT id, title, description, category, user_email, status
            FROM complaints
            WHERE id = %s
            """,
            (complaint_id,)
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Complaint not found"
            )

        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "category": row[3],
            "user_email": row[4],
            "status": row[5]
        }

    finally:
        cursor.close()
        connection.close()


@app.put("/complaints/{complaint_id}/status")
def update_status(
    complaint_id: int,
    update: StatusUpdate,
    authorization: str = Header(None)
):
    user = verify_token(authorization)

    if user.get("role") != "ADMIN":
        send_log(
            "WARNING",
            f"Unauthorized status update attempt by {user.get('email')}"
        )

        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE complaints
            SET status = %s
            WHERE id = %s
            RETURNING id, title, description, category, user_email, status
            """,
            (update.status, complaint_id)
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Complaint not found"
            )

        connection.commit()

        send_log(
            "INFO",
            f"Complaint {complaint_id} status updated to {update.status}"
        )

        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "category": row[3],
            "user_email": row[4],
            "status": row[5]
        }

    finally:
        cursor.close()
        connection.close()