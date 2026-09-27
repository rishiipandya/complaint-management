import os

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


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def verify_token(authorization: str):
    if not authorization:
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
    return {"message": "Complaint Service is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/complaints")
def create_complaint(
    complaint: ComplaintRequest,
    authorization: str = Header(None)
):
    user = verify_token(authorization)

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