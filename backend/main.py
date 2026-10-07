import os
from contextlib import asynccontextmanager
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException


DATABASE_URL = os.environ["DATABASE_URL"]

SAMPLE_PROJECTS = [
    {
        "number": "DEMO-001",
        "customer": "Example Consulting GmbH",
        "hours": Decimal("10"),
        "rate": Decimal("100"),
    },
    {
        "number": "DEMO-002",
        "customer": "Example Services GmbH",
        "hours": Decimal("8"),
        "rate": Decimal("125"),
    },
]

SAMPLE_PAYMENTS = [
    ("BANK-001", "DEMO-001", Decimal("1190.00")),
    ("BANK-002", "DEMO-002", Decimal("1140.00")),
    ("BANK-003", "DEMO-001", Decimal("25.00")),
    ("BANK-004", "DEMO-002", Decimal("5.00")),
    ("BANK-005", "DEMO-001", Decimal("40.00")),
    ("BANK-006", "DEMO-002", Decimal("3.00")),
    ("BANK-007", "DEMO-001", Decimal("15.00")),
    ("BANK-008", "DEMO-002", Decimal("2.00")),
    ("BANK-009", "DEMO-001", Decimal("60.00")),
    ("BANK-010", "DEMO-002", Decimal("4.00")),
    ("BANK-011", "DEMO-001", Decimal("10.00")),
    ("BANK-012", "DEMO-002", Decimal("1.00")),
    ("BANK-013", "DEMO-001", Decimal("35.00")),
    ("BANK-014", "DEMO-002", Decimal("6.00")),
    ("BANK-015", "DEMO-001", Decimal("20.00")),
    ("BANK-016", "DEMO-002", Decimal("2.00")),
    ("BANK-017", "DEMO-001", Decimal("45.00")),
    ("BANK-018", "DEMO-002", Decimal("3.00")),
    ("BANK-019", "DEMO-001", Decimal("30.00")),
    ("BANK-020", "DEMO-002", Decimal("4.00")),
]


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def record_event(conn, invoice_number, message):
    conn.execute(
        """
        INSERT INTO events (invoice_number, message)
        VALUES (%s, %s)
        """,
        (invoice_number, message),
    )


@asynccontextmanager
async def lifespan(app):
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                number TEXT PRIMARY KEY,
                customer TEXT NOT NULL,
                hours NUMERIC(10, 2) NOT NULL,
                rate NUMERIC(10, 2) NOT NULL,
                net NUMERIC(12, 2) NOT NULL,
                vat NUMERIC(12, 2) NOT NULL,
                total NUMERIC(12, 2) NOT NULL,
                paid NUMERIC(12, 2) NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Open'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                transaction_id TEXT PRIMARY KEY,
                invoice_number TEXT NOT NULL REFERENCES invoices(number),
                amount NUMERIC(12, 2) NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id BIGSERIAL PRIMARY KEY,
                invoice_number TEXT NOT NULL REFERENCES invoices(number),
                message TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
    yield


app = FastAPI(
    title="Aeiforia Workflow Demo",
    description="Interview prototype using fictional data.",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.post("/demo/generate")
def generate_invoices():
    created = 0

    with connect() as conn:
        for project in SAMPLE_PROJECTS:
            net = (project["hours"] * project["rate"]).quantize(
                Decimal("0.01")
            )
            vat = (net * Decimal("0.19")).quantize(Decimal("0.01"))
            total = net + vat

            result = conn.execute(
                """
                INSERT INTO invoices
                    (number, customer, hours, rate, net, vat, total)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (number) DO NOTHING
                RETURNING number
                """,
                (
                    project["number"],
                    project["customer"],
                    project["hours"],
                    project["rate"],
                    net,
                    vat,
                    total,
                ),
            ).fetchone()

            if result:
                created += 1
                record_event(
                    conn,
                    project["number"],
                    "Invoice draft generated from sample time entries.",
                )

    return {"created": created}


@app.get("/invoices")
def list_invoices():
    with connect() as conn:
        return conn.execute(
            """
            SELECT *, total - paid AS outstanding
            FROM invoices
            ORDER BY number
            """
        ).fetchall()


@app.post("/demo/match")
def match_payments():
    imported = 0

    with connect() as conn:
        # Lock invoice rows so simultaneous calls cannot double-process them.
        invoices = conn.execute(
            "SELECT * FROM invoices ORDER BY number FOR UPDATE"
        ).fetchall()

        if len(invoices) < len(SAMPLE_PROJECTS):
            raise HTTPException(
                status_code=409,
                detail="Generate the sample invoices first.",
            )

        for transaction_id, invoice_number, amount in SAMPLE_PAYMENTS:
            result = conn.execute(
                """
                INSERT INTO payments
                    (transaction_id, invoice_number, amount)
                VALUES (%s, %s, %s)
                ON CONFLICT (transaction_id) DO NOTHING
                RETURNING transaction_id
                """,
                (transaction_id, invoice_number, amount),
            ).fetchone()

            if result:
                imported += 1
                record_event(
                    conn,
                    invoice_number,
                    f"Sample bank payment imported: EUR {amount}.",
                )

        for invoice in invoices:
            paid = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS amount
                FROM payments WHERE invoice_number = %s
                """,
                (invoice["number"],),
            ).fetchone()["amount"]

            total = invoice["total"]

            if paid == total:
                status = "Paid"
            elif paid == 0:
                status = "Open"
            else:
                status = "Needs review"

            conn.execute(
                """
                UPDATE invoices SET paid = %s, status = %s
                WHERE number = %s
                """,
                (paid, status, invoice["number"]),
            )

            if status != invoice["status"]:
                record_event(
                    conn,
                    invoice["number"],
                    f"Status changed to {status}. "
                    f"Outstanding amount: EUR {total - paid}.",
                )

    return {"imported": imported}


@app.get("/events")
def list_events():
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM events ORDER BY id DESC"
        ).fetchall()




import logging
from rag import index_knowledge, explain_invoice


@app.post("/knowledge/index")
def index_procedures():
    try:
        return index_knowledge()
    except Exception:
        logging.exception("Knowledge indexing failed")
        raise HTTPException(
            status_code=502,
            detail="Indexing failed. Check backend logs.",
        )


@app.get("/invoices/{number}/explanation")
def invoice_explanation(number: str):
    with connect() as conn:
        invoice = conn.execute(
            "SELECT * FROM invoices WHERE number = %s",
            (number,),
        ).fetchone()

    if not invoice:
        raise HTTPException(404, "Invoice not found.")

    try:
        return explain_invoice(invoice)
    except Exception:
        logging.exception("RAG explanation failed")
        raise HTTPException(
            status_code=502,
            detail="Explanation failed. Check indexing and backend logs.",
        )