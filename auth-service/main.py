import json
import os
import socket
from datetime import datetime, timedelta, timezone

import jwt
import psycopg2
from pwdlib import PasswordHash

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Authentication Service")

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-later")
ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()

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
        "service": "auth-service",
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


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "USER"


class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/")
def root():
    send_log("INFO", "Auth service root endpoint accessed")
    return {"message": "Authentication Service is running"}


@app.get("/health")
def health():
    send_log("INFO", "Auth service health check")
    return {"status": "healthy"}


@app.post("/register")
def register(user: RegisterRequest):
    send_log("INFO", f"Registration attempt for {user.email}")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        hashed_password = password_hash.hash(user.password)

        cursor.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (
                user.name,
                user.email,
                hashed_password,
                user.role
            )
        )

        user_id = cursor.fetchone()[0]
        connection.commit()

        send_log("INFO", f"User registered: {user.email}")

        return {
            "message": "User registered successfully",
            "user_id": user_id,
            "email": user.email,
            "role": user.role
        }

    except psycopg2.errors.UniqueViolation:
        connection.rollback()
        send_log("WARNING", f"Duplicate user registration: {user.email}")

        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    finally:
        cursor.close()
        connection.close()


@app.post("/login")
def login(user: LoginRequest):
    send_log("INFO", f"Login attempt for {user.email}")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT id, email, password, role
            FROM users
            WHERE email = %s
            """,
            (user.email,)
        )

        stored_user = cursor.fetchone()

        if not stored_user:
            send_log("WARNING", f"Login failed: {user.email}")

            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        user_id, email, stored_password, role = stored_user

        if not password_hash.verify(user.password, stored_password):
            send_log("WARNING", f"Invalid password: {user.email}")

            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }

        token = jwt.encode(
            payload,
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        send_log("INFO", f"Login successful: {user.email}")

        return {
            "message": "Login successful",
            "access_token": token,
            "token_type": "bearer"
        }

    finally:
        cursor.close()
        connection.close()