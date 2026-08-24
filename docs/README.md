# PhishGuard documentation

Four documents. Start wherever matches what you need.

| | |
|---|---|
| **[SETUP.md](SETUP.md)** | Get it running. Two paths: demo mode with no Google account (5 min), or live Gmail with OAuth (15 min). Configuration reference and troubleshooting. |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | How the system fits together, the five decisions that shaped it, and what is deliberately not in it. |
| **[BACKEND.md](BACKEND.md)** | What FastAPI, SQLAlchemy, Pydantic, uvicorn, and the Google client libraries each *do*, why each was chosen, and a file-by-file tour of the code. |
| **[DETECTION.md](DETECTION.md)** | SPF, DKIM, and DMARC explained from first principles. Every detection signal, its weight and the reasoning behind it, how to tune, and honest limitations. |
| **[FRONTEND.md](FRONTEND.md)** | What React, Vite, and Recharts each do and why they are here, how the dashboard is organised, and the visual-design rules it follows. |

## Suggested reading order

**To use it:** SETUP → DETECTION (part 4, tuning).

**To understand it:** ARCHITECTURE → DETECTION → BACKEND → FRONTEND.

**To review the code:** ARCHITECTURE first — it explains the constraints
everything else follows from — then whichever half you are reading.
