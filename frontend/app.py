import os
from decimal import Decimal
from urllib.parse import quote

import requests
from flask import (
    Flask,
    redirect,
    render_template_string,
    request,
    url_for,
)


app = Flask(__name__)
API_URL = os.environ.get("API_URL", "http://backend:8000")


@app.template_filter("money")
def money(value):
    return f"€{Decimal(str(value)):,.2f}"


PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoice Workflow Demo</title>
    <style>
        * { box-sizing: border-box; }

        body {
            margin: 0;
            background: #f3f6fb;
            color: #172338;
            font-family: Arial, sans-serif;
        }

        main {
            max-width: 1150px;
            margin: 45px auto;
            padding: 0 24px;
        }

        .label {
            color: #5265d9;
            font-weight: bold;
            font-size: 12px;
            letter-spacing: 2px;
        }

        h1 { font-size: 36px; margin-bottom: 10px; }
        h2 { margin-top: 0; font-size: 20px; }

        .subtitle {
            color: #64748b;
            line-height: 1.6;
        }

        .cards {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 18px;
            margin: 28px 0;
        }

        .card, .panel {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 24px;
        }

        .card span { color: #64748b; font-size: 14px; }

        .card strong {
            display: block;
            font-size: 30px;
            margin-top: 12px;
        }

        .actions, .rag-form {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
        }

        .actions { margin: 24px 0; }

        button, .refresh {
            border: 0;
            border-radius: 8px;
            padding: 13px 20px;
            background: #4556d8;
            color: white;
            font-weight: bold;
            cursor: pointer;
            text-decoration: none;
            font-size: 14px;
        }

        button:disabled { opacity: 0.5; cursor: default; }
        .secondary { background: #172338; }

        .refresh {
            background: white;
            color: #4556d8;
            border: 1px solid #ddd;
        }

        select {
            padding: 12px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            font-size: 14px;
            max-width: 100%;
        }

        .panel { margin-bottom: 22px; overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }

        th, td {
            text-align: left;
            padding: 15px 10px;
            border-bottom: 1px solid #eef2f7;
            font-size: 14px;
        }

        th {
            color: #64748b;
            font-size: 12px;
            text-transform: uppercase;
        }

        .badge {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            white-space: nowrap;
        }

        .paid { background: #dcfce7; color: #166534; }
        .review { background: #fff1d6; color: #92400e; }
        .open { background: #e0e7ff; color: #3730a3; }

        .message {
            padding: 15px;
            background: #e0e7ff;
            border-radius: 8px;
            margin: 20px 0;
        }

        .error { background: #fee2e2; color: #991b1b; }
        .empty { color: #64748b; padding: 20px 0; }

        .event {
            padding: 12px 0;
            border-bottom: 1px solid #eef2f7;
        }

        .event small {
            display: block;
            color: #64748b;
            margin-top: 5px;
        }

        footer {
            color: #64748b;
            font-size: 12px;
            line-height: 1.8;
            padding-bottom: 25px;
        }

        @media(max-width: 650px) {
            .cards { grid-template-columns: 1fr; }
            h1 { font-size: 28px; }
        }
    </style>
</head>
<body>
<main>
    <div class="label">YOUSSEF HENIN · INTERVIEW PROTOTYPE</div>

    <h1>Invoice Automation Workflow</h1>

    <p class="subtitle">
        Demonstration inspired by Aeiforia's project description.<br>
        Sample time entries → invoice records → payment matching
        → exception explanation.
    </p>

    {% if message %}
        <div class="message">{{ message }}</div>
    {% endif %}

    {% if error %}
        <div class="message error">{{ error }}</div>
    {% endif %}

    <div class="cards">
        <div class="card">
            <span>Invoice records</span>
            <strong>{{ invoices | length }}</strong>
        </div>
        <div class="card">
            <span>Matched as paid</span>
            <strong>{{ paid_count }}</strong>
        </div>
        <div class="card">
            <span>Cases needing review</span>
            <strong>{{ review_count }}</strong>
        </div>
    </div>

    <div class="actions">
        <form method="post" action="{{ url_for('run_action', action='generate') }}">
            <button>1. Generate sample invoices</button>
        </form>

        <form method="post" action="{{ url_for('run_action', action='match') }}">
            <button class="secondary">2. Match sample payments</button>
        </form>

        <a class="refresh" href="{{ url_for('index') }}">Refresh</a>
    </div>

    <section class="panel">
        <h2>Invoices & payment status</h2>

        {% if invoices %}
        <table>
            <thead>
                <tr>
                    <th>Invoice</th>
                    <th>Customer</th>
                    <th>Hours</th>
                    <th>Total</th>
                    <th>Paid</th>
                    <th>Outstanding</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for invoice in invoices %}
                <tr>
                    <td><b>{{ invoice.number }}</b></td>
                    <td>{{ invoice.customer }}</td>
                    <td>{{ invoice.hours }}</td>
                    <td>{{ invoice.total | money }}</td>
                    <td>{{ invoice.paid | money }}</td>
                    <td>{{ invoice.outstanding | money }}</td>
                    <td>
                        <span class="badge {{
                            'paid' if invoice.status == 'Paid'
                            else 'review' if invoice.status == 'Needs review'
                            else 'open'
                        }}">{{ invoice.status }}</span>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        <p class="subtitle">
            A negative outstanding amount indicates an overpayment.
        </p>
        {% else %}
        <div class="empty">
            Click “Generate sample invoices” to create demonstration records.
        </div>
        {% endif %}
    </section>

    <section class="panel">
        <h2>RAG payment explanation</h2>
        <p class="subtitle">
            Retrieve relevant sample procedures from Qdrant,
            then generate an explanation with Gemini.
        </p>

        {% if invoices %}
        <form class="rag-form" method="post" action="{{ url_for('explain') }}">
            <select name="number" required aria-label="Select invoice">
                {% for invoice in invoices %}
                <option value="{{ invoice.number }}">
                    {{ invoice.number }} — {{ invoice.status }}
                </option>
                {% endfor %}
            </select>
            <button>Explain payment result</button>
        </form>
        {% else %}
        <div class="empty">Generate invoices before requesting an explanation.</div>
        {% endif %}
    </section>

    <section class="panel">
        <h2>Processing history</h2>

        {% for event in events %}
        <div class="event">
            <b>{{ event.invoice_number }}</b> — {{ event.message }}
            <small>{{ event.created_at }}</small>
        </div>
        {% else %}
        <div class="empty">Processing actions will appear here.</div>
        {% endfor %}
    </section>

    <footer>
        Fictional data · Invoice records are drafts, not validated e-invoices.<br>
        Flask · FastAPI · PostgreSQL · Qdrant · Gemini · Docker Compose
    </footer>
</main>
</body>
</html>
"""


EXPLANATION_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>RAG Payment Explanation</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f3f6fb;
            color: #172338;
            margin: 0;
        }

        main {
            max-width: 900px;
            margin: 45px auto;
            padding: 0 24px;
        }

        a { color: #4556d8; }
        h1 { margin-top: 30px; }

        .answer, .source {
            background: white;
            padding: 24px;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            margin-bottom: 18px;
        }

        .text {
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            line-height: 1.7;
        }

        .note { color: #64748b; line-height: 1.6; }
    </style>
</head>
<body>
<main>
    <a href="{{ url_for('index') }}">← Back to dashboard</a>

    <h1>Payment explanation — {{ number }}</h1>

    <p class="note">
        Generated from fictional demonstration procedures.
        Review the explanation before taking action.
    </p>

    <div class="answer text">{{ explanation }}</div>

    <h2>Retrieved source passages</h2>

    {% for source in sources %}
    <div class="source">
        <h3>[{{ loop.index }}] {{ source.source }}</h3>
        <div class="text">{{ source.passage }}</div>
    </div>
    {% endfor %}
</main>
</body>
</html>
"""


@app.get("/")
def index():
    invoices = []
    events = []
    error = request.args.get("error", "")

    try:
        response = requests.get(f"{API_URL}/invoices", timeout=10)
        response.raise_for_status()
        invoices = response.json()

        response = requests.get(f"{API_URL}/events", timeout=10)
        response.raise_for_status()
        events = response.json()

    except (requests.RequestException, ValueError):
        error = "Cannot load backend data. Check the backend container logs."

    return render_template_string(
        PAGE,
        invoices=invoices,
        events=events,
        paid_count=sum(i["status"] == "Paid" for i in invoices),
        review_count=sum(i["status"] == "Needs review" for i in invoices),
        message=request.args.get("message", ""),
        error=error,
    )


@app.post("/action/<action>")
def run_action(action):
    endpoints = {
        "generate": "/demo/generate",
        "match": "/demo/match",
    }

    if action not in endpoints:
        return "Unknown action", 404

    try:
        response = requests.post(
            f"{API_URL}{endpoints[action]}",
            timeout=30,
        )

        if not response.ok:
            return redirect(url_for(
                "index",
                error=f"Action failed (HTTP {response.status_code}). "
                      "Generate invoices first; check backend logs if needed.",
            ))

        result = response.json()

        if action == "generate":
            message = f"Created {result['created']} new invoice records."
        else:
            message = (
                f"Imported {result['imported']} new payments "
                "and checked matches."
            )

        return redirect(url_for("index", message=message))

    except (requests.RequestException, ValueError):
        return redirect(url_for(
            "index",
            error="Could not complete the action. Check the backend container.",
        ))


@app.post("/explain")
def explain():
    number = request.form.get("number", "").strip()

    if not number:
        return redirect(url_for(
            "index",
            error="Select an invoice first.",
        ))

    try:
        response = requests.get(
            f"{API_URL}/invoices/{quote(number, safe='')}/explanation",
            timeout=150,
        )

        if not response.ok:
            return redirect(url_for(
                "index",
                error=f"RAG request failed (HTTP {response.status_code}). "
                      "Check knowledge indexing and backend logs.",
            ))

        result = response.json()

        return render_template_string(
            EXPLANATION_PAGE,
            number=number,
            explanation=result["explanation"],
            sources=result["sources"],
        )

    except (requests.RequestException, ValueError, KeyError):
        return redirect(url_for(
            "index",
            error="Could not load the RAG explanation. Check backend logs.",
        ))