from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from psycopg.errors import CheckViolation, UniqueViolation
from psycopg.rows import dict_row

from banking.config import dsn
from banking.logging import log
from banking.models import CreateTransaction, TransactionRow, UpdateTransaction

app = FastAPI(title="Synthetic Banking API", version="0.1.0")


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(request: Request, error: psycopg.OperationalError) -> JSONResponse:
    log("source_unavailable", path=request.url.path, error_type=type(error).__name__)
    return JSONResponse(status_code=503, content={"detail": "Source database unavailable"})


@app.get("/health")
def health() -> dict[str, str]:
    with psycopg.connect(dsn("source")) as conn:
        conn.execute("SELECT 1 FROM bank.transactions LIMIT 1")
    return {"status": "ok"}


@app.post("/transactions", status_code=201, response_model=TransactionRow)
def create(body: CreateTransaction) -> dict:
    try:
        with psycopg.connect(dsn("source"), row_factory=dict_row) as conn:
            return conn.execute("""
                INSERT INTO bank.transactions (transaction_id, account_id, amount_minor, currency, status)
                VALUES (%(transaction_id)s, %(account_id)s, %(amount_minor)s, %(currency)s, 'pending')
                RETURNING *
            """, body.model_dump()).fetchone()
    except UniqueViolation as error:
        raise HTTPException(409, "Transaction ID already used") from error


@app.patch("/transactions/{transaction_id}", response_model=TransactionRow)
def update(transaction_id: UUID, body: UpdateTransaction) -> dict:
    try:
        with psycopg.connect(dsn("source"), row_factory=dict_row) as conn:
            row = conn.execute("""
                UPDATE bank.transactions
                SET amount_minor = COALESCE(%(amount_minor)s, amount_minor),
                    status = COALESCE(%(status)s, status)
                WHERE transaction_id = %(id)s AND version = %(expected_version)s
                RETURNING *
            """, body.model_dump() | {"id": transaction_id}).fetchone()
            if row is None:
                raise HTTPException(409, "Missing transaction or stale version")
            return row
    except CheckViolation as error:
        raise HTTPException(422, "Invalid transaction change") from error


@app.delete("/transactions/{transaction_id}", status_code=204)
def delete(transaction_id: UUID, expected_version: int) -> Response:
    with psycopg.connect(dsn("source")) as conn:
        result = conn.execute("""
            DELETE FROM bank.transactions WHERE transaction_id = %s AND version = %s
        """, (transaction_id, expected_version))
        if result.rowcount != 1:
            raise HTTPException(409, "Missing transaction or stale version")
    return Response(status_code=204)
