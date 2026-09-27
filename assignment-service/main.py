import os

import jwt
import httpx
import psycopg2

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="Assignment Service")

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-later")
ALGORITHM = "HS256"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5433")),
    "database": os.getenv("DB_NAME", "complaint_management"),
    "user": os.getenv("DB_USER", "complaint_app"),
    "password": os.getenv("DB_PASSWORD", "complaint123")
}

NOTIFICATION_SERVICE_URL = os.getenv(
    "NOTIFICATION_SERVICE_URL",
    "http://127.0.0.1:8004"
)


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def verify_admin_token(authorization: str):
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
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        if payload.get("role") != "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )

        return payload

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )


class AssignmentRequest(BaseModel):
    complaint_id: int
    assigned_to: str
    user_email: str


@app.get("/")
def root():
    return {"message": "Assignment Service is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/assignments")
def create_assignment(
    assignment: AssignmentRequest,
    authorization: str = Header(None)
):
    verify_admin_token(authorization)

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO assignments
            (complaint_id, assigned_to, user_email)
            VALUES (%s, %s, %s)
            RETURNING id, complaint_id, assigned_to, user_email
            """,
            (
                assignment.complaint_id,
                assignment.assigned_to,
                assignment.user_email
            )
        )

        row = cursor.fetchone()
        connection.commit()

        assignment_data = {
            "id": row[0],
            "complaint_id": row[1],
            "assigned_to": row[2],
            "user_email": row[3]
        }

        notification = {
            "user_email": assignment.user_email,
            "message": (
                f"Your complaint #{assignment.complaint_id} "
                f"has been assigned to {assignment.assigned_to}."
            )
        }

        try:
            response = httpx.post(
                f"{NOTIFICATION_SERVICE_URL}/notifications",
                json=notification
            )

            response.raise_for_status()

        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Notification Service is unavailable"
            )

        return {
            "message": "Complaint assigned successfully",
            "assignment": assignment_data
        }

    finally:
        cursor.close()
        connection.close()


@app.get("/assignments/{complaint_id}")
def get_assignment(
    complaint_id: int,
    authorization: str = Header(None)
):
    verify_admin_token(authorization)

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT id, complaint_id, assigned_to, user_email
            FROM assignments
            WHERE complaint_id = %s
            """,
            (complaint_id,)
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Assignment not found"
            )

        return {
            "id": row[0],
            "complaint_id": row[1],
            "assigned_to": row[2],
            "user_email": row[3]
        }

    finally:
        cursor.close()
        connection.close()