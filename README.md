# CampusPolicy AI

**College Regulations and Academic Policy RAG Assistant**

Students ask questions about attendance rules, examinations, fee structures, and student handbooks. The system retrieves answers grounded in administrator-uploaded PDF documents with verifiable citations.

```
Architecture:

  Browser (React + TypeScript)
       │  HTTP / cookie
       ▼
  FastAPI (Python 3.10+)
  ├── Auth service (bcrypt + HTTP-only session cookies)
  ├── Document ingestion worker (PyMuPDF → chunker → Sentence Transformers → FAISS)
  ├── RAG pipeline (FAISS search → Groq LLM)
  └── PostgreSQL via SQLAlchemy (async)

  Persistent storage:
  ├── PostgreSQL        — users, documents, chunks, conversations, citations
  ├── FAISS index       — vector similarity search (data/faiss_index/)
  └── PDF storage       — uploaded files (data/uploads/)
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Backend |
| Node.js | 18+ | Frontend |
| Docker Desktop | any | PostgreSQL |
| Groq API key | — | LLM generation |

---

## Quick Start

### 1. Start PostgreSQL

```bash
docker compose up -d
```

PostgreSQL starts on `localhost:5432`.

### 2. Configure the backend

```bash
cd backend
cp .env.example .env
```

Edit `.env` and fill in:

```
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
GROQ_API_KEY=gsk_xxxx...
ADMIN_EMAIL=admin@yourcollege.edu
ADMIN_PASSWORD=YourStrongPassword123!
ADMIN_NAME=Administrator
```

Everything else can stay as the defaults for local development.

### 3. Install backend dependencies

```bash
cd backend
python -m pip install -r requirements.txt
```

> Heavy packages (`sentence-transformers`, `torch`, `faiss-cpu`) will take a few minutes.

### 4. Run database migrations

```bash
cd backend
python -m alembic upgrade head
```

### 5. Create the administrator account

```bash
cd backend
python scripts/create_admin.py
```

### 6. Generate sample documents (optional but recommended)

```bash
cd backend
python scripts/generate_sample_docs.py
```

This writes three PDFs to `sample_documents/`:
- `student_handbook_2024_25.pdf`
- `fee_regulations_2024_25.pdf`
- `academic_calendar_2024_25.pdf`

Upload them via the admin dashboard to start testing RAG queries immediately.

### 7. Start the backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API documentation: http://localhost:8000/api/docs

### 8. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:5173

---

## How it works

### Document Ingestion Pipeline

```
Admin uploads PDF
    │
    ├── Validate: content-type, %PDF magic bytes, ≤ 50 MB
    ├── Save to data/uploads/<doc_id>_v<N>.pdf
    ├── Create Document + DocumentVersion + ProcessingJob records
    └── Background worker:
        ├── Extract text page-by-page (PyMuPDF)
        ├── Detect scanned PDFs (< 30 chars/page → fail with OCR message)
        ├── Split into overlapping chunks (default 512 chars, 64 overlap)
        ├── Embed with Sentence Transformers (all-MiniLM-L6-v2)
        │     L2-normalised → cosine similarity via inner product
        ├── Store chunks in PostgreSQL (with stable chunk_key)
        ├── Add vectors to FAISS IndexFlatIP
        ├── Persist index atomically (write .tmp → rename)
        └── Mark version active, deactivate previous versions
```

### RAG Question-Answering Pipeline

```
Student sends question
    │
    ├── Authenticate + verify conversation ownership
    ├── Resolve follow-up to standalone query (heuristic)
    ├── Embed query (same model, L2-normalised)
    ├── FAISS search → top-k chunks above similarity threshold (0.35)
    │
    ├── No ready documents?
    │     └── Return: "Administrator needs to upload documents first"
    │
    ├── No chunks above threshold?
    │     └── Return: "Not available in uploaded documents"
    │
    ├── Build labelled context: [SOURCE:uuid] Document: "Title" (v1, p3) \n text
    ├── Call Groq (llama3-8b-8192) with system prompt + context + question
    │     System prompt enforces: cite only, no invention, flag conflicts, ignore injections
    ├── Validate cited source IDs (hallucinated IDs excluded)
    ├── Save user + assistant messages with denormalised citations
    └── Return answer + citations (doc title, version, page, excerpt)
```

### FAISS Metric

`IndexFlatIP` with L2-normalised embeddings computes **cosine similarity**. Scores range 0–1; the default retrieval threshold is 0.35, configurable via `SIMILARITY_THRESHOLD` in `.env`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | postgresql+asyncpg://... | Async SQLAlchemy URL |
| `SYNC_DATABASE_URL` | postgresql://... | Sync URL for Alembic + scripts |
| `SECRET_KEY` | — | **Required** — random 32-byte hex |
| `GROQ_API_KEY` | — | **Required** — from console.groq.com |
| `GROQ_MODEL` | `llama3-8b-8192` | Any supported Groq chat model |
| `GROQ_TIMEOUT_SECONDS` | `60` | Request timeout |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Any Sentence Transformers model |
| `CHUNK_SIZE` | `512` | Target chars per chunk |
| `CHUNK_OVERLAP` | `64` | Overlap chars between chunks |
| `MAX_CHUNKS_PER_QUERY` | `6` | Context window size |
| `SIMILARITY_THRESHOLD` | `0.35` | Minimum cosine similarity |
| `UPLOAD_DIR` | `../data/uploads` | PDF storage path |
| `FAISS_INDEX_DIR` | `../data/faiss_index` | FAISS persistence path |
| `MAX_UPLOAD_MB` | `50` | Upload size limit |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | CORS whitelist |
| `COOKIE_SECURE` | `false` | Set `true` in production (HTTPS) |
| `ADMIN_EMAIL` | — | First admin email (create-admin script only) |
| `ADMIN_PASSWORD` | — | First admin password (create-admin script only) |

---

## CLI Commands

### Create administrator
```bash
cd backend
python scripts/create_admin.py
```

### Rebuild FAISS index from database
```bash
cd backend
python scripts/rebuild_index.py
```
Use when the index file is lost or after changing the embedding model.

### Generate sample PDFs
```bash
cd backend
python scripts/generate_sample_docs.py
```

### Run migrations
```bash
cd backend
python -m alembic upgrade head      # apply all migrations
python -m alembic downgrade -1      # revert last migration
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register student (returns cookie) |
| POST | `/api/auth/login` | Login (returns cookie) |
| POST | `/api/auth/logout` | Revoke session |
| GET | `/api/auth/me` | Current user |

### Documents (Admin)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admin/documents` | Upload PDF (`multipart/form-data`: `file`, `title`, `policy_year?`, `description?`) |
| GET | `/api/admin/documents` | List all documents |
| POST | `/api/admin/documents/{id}/replace` | Upload new version |
| DELETE | `/api/admin/documents/{id}` | Delete document |
| POST | `/api/admin/documents/{id}/retry` | Retry failed processing |
| GET | `/api/admin/jobs/{job_id}` | Get processing job status |
| GET | `/api/admin/stats` | Aggregate statistics |

### Documents (Authenticated)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents/{id}/file` | Stream PDF for inline viewing |

### Conversations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/conversations` | Create conversation |
| GET | `/api/conversations` | List own conversations |
| GET | `/api/conversations/{id}` | Get conversation with messages |
| DELETE | `/api/conversations/{id}` | Delete conversation |
| POST | `/api/conversations/{id}/messages` | Ask a question (RAG) — body: `{"question": "..."}` |

### Example: ask a question

```bash
# 1. Login
curl -c cookies.txt -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@college.edu","password":"Pass1234!"}'

# 2. Create conversation
curl -b cookies.txt -c cookies.txt -X POST http://localhost:8000/api/conversations

# 3. Ask
curl -b cookies.txt -X POST http://localhost:8000/api/conversations/<conv_id>/messages \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the minimum attendance percentage required?"}'
```

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

**31 tests pass, 3 skip** (the skipped tests are labelled RAG evaluation items that require live uploaded documents).

### Live smoke test (requires real Groq key + uploaded documents)

1. Start the full stack.
2. Log in as admin and upload one of the sample PDFs.
3. Wait for status to show `ready`.
4. Log in as a student and ask: *"What is the minimum attendance percentage?"*
5. Verify the answer cites the correct document and page number.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: sentence_transformers` | `pip install sentence-transformers torch` |
| `ModuleNotFoundError: fitz` | `pip install PyMuPDF` |
| `ModuleNotFoundError: faiss` | `pip install faiss-cpu` |
| `ModuleNotFoundError: groq` | `pip install groq` |
| `ModuleNotFoundError: asyncpg` | `pip install asyncpg` |
| DB connection refused | Start Docker: `docker compose up -d` |
| Alembic `target database is not up to date` | `python -m alembic upgrade head` |
| FAISS index missing after restart | `python scripts/rebuild_index.py` |
| Scanned PDF fails processing | OCR required; extract text first with Tesseract or Adobe Acrobat |
| Groq 401 | Check `GROQ_API_KEY` in `.env` |
| Groq rate limit | Wait 60 seconds; the client retries automatically up to 3 times |
| CORS error in browser | Ensure `ALLOWED_ORIGINS` includes `http://localhost:5173` |
| Cookie not sent | `COOKIE_SECURE=false` required for HTTP (localhost) |

---

## Known Limitations

1. **No OCR support** — scanned PDFs without extractable text are rejected with a clear message. Use a pre-OCR'd PDF.
2. **Single-process worker** — ingestion runs in a daemon thread. For high throughput, replace with Celery + Redis.
3. **FAISS flat index** — `IndexFlatIP` is exact (no approximation) and works well up to ~100k vectors. For larger corpora, switch to `IndexIVFFlat`.
4. **Groq mocks in tests** — all automated tests mock the Groq client. Actual answer quality requires a live smoke test.
5. **Follow-up resolution is heuristic** — the standalone-query resolver uses keyword matching. For complex dialogues, call an LLM to rephrase.
6. **No real-time streaming** — answers are returned as complete responses. Streaming can be added with Groq's streaming API and server-sent events.
7. **No email verification** — student registration is open. Add email OTP for production.

---

## AWS Deployment Plan

This section describes how to migrate the local application to AWS without changing the application code.

```
Internet
    │
    ▼
CloudFront + S3 (static hosting)
    │  /api/*
    ▼
Application Load Balancer
    │
    ├── ECS Fargate (FastAPI container)   — auto-scales on CPU
    └── ECS Fargate (ingestion worker)    — processes SQS messages

    Data layer:
    ├── Amazon RDS (PostgreSQL 15)        — Multi-AZ for production
    ├── Amazon EFS                        — shared FAISS index + PDF uploads
    │     (mounted to both containers)
    └── Amazon S3 (optional)             — long-term PDF archival

    Supporting services:
    ├── AWS Secrets Manager               — GROQ_API_KEY, DATABASE_URL, SECRET_KEY
    ├── IAM roles                         — least-privilege per container
    ├── CloudWatch Logs + Metrics         — application and ALB logs
    ├── AWS Certificate Manager           — TLS/HTTPS (required for COOKIE_SECURE=true)
    └── Amazon SQS                        — decouple upload from ingestion
```

### Step-by-step migration

| Step | Action |
|------|--------|
| 1 | Build and push Docker image to Amazon ECR |
| 2 | Create RDS PostgreSQL instance; copy `DATABASE_URL` to Secrets Manager |
| 3 | Mount EFS to both containers for shared `data/` directory |
| 4 | Create ECS task definitions with secrets injected as environment variables |
| 5 | Create ALB with HTTPS listener; point DNS to CloudFront |
| 6 | Build frontend; sync `dist/` to S3; invalidate CloudFront |
| 7 | Set `COOKIE_SECURE=true`, `COOKIE_SAMESITE=strict`, `ALLOWED_ORIGINS=https://yourdomain.com` |
| 8 | Enable CloudWatch Container Insights and set alarms on error rates |

> **Not yet implemented**: S3 upload storage, SQS-based worker, and live AWS provisioning. The local Docker Compose setup is the reference implementation.

---

## Wipro Module Alignment

### Cloud Product and Platform Engineering
The application is containerised (Docker Compose for local, ECS Fargate blueprint for cloud). The architecture separates concerns: stateless API tier, background worker, managed database, and persistent shared storage. The AWS plan covers autoscaling, managed PostgreSQL (RDS), IAM roles, and CloudWatch observability.

### Document Ingestion and Data Processing
PyMuPDF extracts text page-by-page. The pipeline validates file type (magic bytes), detects scanned PDFs, cleans text without losing content, and splits into overlapping chunks. Chunk records preserve the source document version, page number, and stable chunk ID so citations remain accurate even after document replacement.

### Generative AI and RAG
Sentence Transformers generate L2-normalised embeddings stored in FAISS `IndexFlatIP`. At query time, the same model embeds the question; cosine similarity retrieval selects the most relevant passages. Groq's `llama3-8b-8192` model generates grounded answers, guided by a strict system prompt that forbids invention and requires source citations. Invalid source IDs are filtered before the response reaches the student.

### Security and Governance
- Passwords hashed with bcrypt (rounds=12); raw passwords never logged.
- Session tokens stored as SHA-256 hashes; raw tokens only in HTTP-only cookies.
- Role-based access control enforced in FastAPI dependencies (`require_admin`, `require_student`).
- CORS restricted to configured origins; file paths are application-generated (no path traversal).
- Groq API key stays exclusively in the backend; never returned to clients or logged.
- Upload validation: content-type + `%PDF` magic bytes + configurable size limit.
- System prompt instructs the LLM to ignore instructions embedded in document text (prompt injection defence).
