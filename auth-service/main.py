from datetime import datetime, timedelta, timezone
import os

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
    return {"message": "Authentication Service is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/register")
def register(user: RegisterRequest):
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

        return {
            "message": "User registered successfully",
            "user_id": user_id,
            "email": user.email,
            "role": user.role
        }

    except psycopg2.errors.UniqueViolation:
        connection.rollback()
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    finally:
        cursor.close()
        connection.close()


@app.post("/login")
def login(user: LoginRequest):
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
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        user_id, email, stored_password, role = stored_user

        if not password_hash.verify(user.password, stored_password):
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

        return {
            "message": "Login successful",
            "access_token": token,
            "token_type": "bearer"
        }

    finally:
        cursor.close()
        connection.close()