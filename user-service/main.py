import os

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


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


@app.get("/")
def root():
    return {"message": "User Service is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/users/{email}")
def get_user(email: str):
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