# PhishGuard documentation

Five documents. Start wherever matches what you need.

| | |
|---|---|
| **[SETUP.md](SETUP.md)** | Get it running. Two paths: demo mode with no Google account (5 min), or live Gmail with OAuth (15 min). Configuration reference and troubleshooting. |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | How the system fits together, the five decisions that shaped it, and what is deliberately not in it. |
| **[BACKEND.md](BACKEND.md)** | What FastAPI, SQLAlchemy, Pydantic, uvicorn, and the Google client libraries each *do*, why each was chosen, and a file-by-file tour of the code. |
| **[DETECTION.md](DETECTION.md)** | SPF, DKIM, and DMARC explained from first principles. Every detection signal, its weight and the reasoning behind it, how to tune, and honest limitations. |
| **[FRONTEND.md](FRONTEND.md)** | What React, Vite, and Recharts each do and why they are here, how the dashboard is organised, and the visual-design rules it follows. |

Two more live next to the code they describe:

| | |
|---|---|
| **[../scripts/README.md](../scripts/README.md)** | The launcher scripts and the logon task — running PhishGuard without a terminal. |
| **[../extension/README.md](../extension/README.md)** | The Chrome extension: what it shows, what each permission is for, and why it cannot start the server. |

## Suggested reading order

**To use it:** SETUP → DETECTION (part 4, tuning) → DETECTION part 5 for what
real mail actually did to the detector.

**To understand it:** ARCHITECTURE → DETECTION → BACKEND → FRONTEND.

**To review the code:** ARCHITECTURE first — it explains the constraints
everything else follows from — then whichever half you are reading.
