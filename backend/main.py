"""
Block 3: FastAPI Server with SSE Streaming
- POST /generate  → kicks off the crew in a background thread
- GET  /stream/{job_id} → SSE stream of agent status events + final result
"""
import os
import uuid
import json
import threading
from queue import Queue, Empty
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

# LangSmith tracing — just set env vars, LangChain picks them up automatically
os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
os.environ.setdefault("LANGCHAIN_PROJECT", "b2b-outreach-engine")
os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGSMITH_API_KEY", "")

from crew_logic import run_crew  # import after env is set so LangSmith activates

app = FastAPI(title="B2B Outreach Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for easy deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store: job_id → Queue of SSE events
# ponytail: simple dict is fine for a single-user prototype; replace with Redis for multi-user
_jobs: dict[str, Queue] = {}


class GenerateRequest(BaseModel):
    company: str
    target_role: str
    your_offering: str


def _run_crew_in_thread(job_id: str, company: str, target_role: str, your_offering: str):
    """Runs the crew and pushes SSE events into the job queue."""
    q = _jobs[job_id]

    def emit(event: str, data: dict):
        q.put(f"event: {event}\ndata: {json.dumps(data)}\n\n")

    try:
        emit("status", {"agent": "Researcher", "message": f"Searching the web for {company}..."})
        # CrewAI is synchronous; we run it here and emit checkpoints around it.
        # For per-agent granularity, CrewAI's step_callback fires after each agent step.
        result = run_crew(
            company=company,
            target_role=target_role,
            your_offering=your_offering,
        )
        emit("status", {"agent": "Analyst", "message": "Identifying pain points..."})
        emit("status", {"agent": "Writer", "message": "Drafting personalized email..."})
        emit("result", result)
    except Exception as e:
        emit("error", {"message": str(e)})
    finally:
        q.put(None)  # sentinel — tells the SSE generator to close


@app.post("/generate")
def generate(req: GenerateRequest) -> dict:
    """Start a crew job. Returns a job_id to stream from."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = Queue()
    t = threading.Thread(
        target=_run_crew_in_thread,
        args=(job_id, req.company, req.target_role, req.your_offering),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id}


@app.get("/stream/{job_id}")
def stream(job_id: str):
    """SSE endpoint. Frontend connects here after getting a job_id."""
    if job_id not in _jobs:
        return {"error": "Unknown job"}

    def event_generator():
        q = _jobs[job_id]
        while True:
            try:
                msg = q.get(timeout=10)
                if msg is None:
                    break
                yield msg
            except Empty:
                yield "event: ping\ndata: {}\n\n"  # keep-alive every 10s
        del _jobs[job_id]

    return StreamingResponse(event_generator(), media_type="text/event-stream")
