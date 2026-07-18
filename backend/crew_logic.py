"""
Block 2: CrewAI Orchestration
- 3 agents: Researcher, Analyst, Writer
- Uses MCP server (mcp_server.py) as tool source via MCPServerAdapter
- Pydantic v2 structured output so frontend gets clean JSON, not freeform text
- LangSmith tracing auto-enabled via env vars
"""
import os
import sys
from pathlib import Path
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process
from crewai_tools import MCPServerAdapter
import litellm
from mcp import StdioServerParameters

# Tell LiteLLM to strip unsupported API parameters
litellm.drop_params = True

# ── Resilient litellm patch ───────────────────────────────────────────────────
# ponytail: single patch handles three Groq-specific issues:
#   1. Strip cache_breakpoint from messages (CrewAI injects it, Groq rejects it)
#   2. Retry on rate limits with exponential backoff
#   3. Retry on tool_use_failed (Llama 3.3 intermittently hallucinates XML tool calls)
# Upgrade path: replace Groq with a provider that doesn't need any of this.
import time as _time
import logging as _logging

_log = _logging.getLogger(__name__)
_original_completion = litellm.completion
_MAX_RETRIES = 4

def _patched_completion(*args, **kwargs):
    if "messages" in kwargs:
        for msg in kwargs.get("messages", []):
            if isinstance(msg, dict):
                msg.pop("cache_breakpoint", None)

    for attempt in range(_MAX_RETRIES):
        try:
            return _original_completion(*args, **kwargs)
        except litellm.RateLimitError as e:
            wait = min(2 ** attempt, 10)
            _log.warning(f"Rate limited (attempt {attempt+1}/{_MAX_RETRIES}), waiting {wait}s...")
            _time.sleep(wait)
            if attempt == _MAX_RETRIES - 1:
                raise
        except litellm.BadRequestError as e:
            if "tool_use_failed" in str(e):
                _log.warning(f"Tool call format error (attempt {attempt+1}/{_MAX_RETRIES}), retrying...")
                _time.sleep(0.5)
                if attempt == _MAX_RETRIES - 1:
                    raise
            else:
                raise  # non-retryable bad request

    return _original_completion(*args, **kwargs)  # fallback, shouldn't reach here

litellm.completion = _patched_completion
litellm.success_callbacks = ["langsmith"]
litellm.failure_callbacks = ["langsmith"]

os.environ.setdefault("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
LLM = "groq/llama-3.3-70b-versatile"

# ── Pydantic output schemas ───────────────────────────────────────────────────
class ResearchOutput(BaseModel):
    company_name: str
    recent_news: list[str] = Field(description="3-5 recent news items or blog posts")
    tech_stack: list[str] = Field(description="Known technologies the company uses")
    pain_points: list[str] = Field(description="Inferred technical or business pain points")
    key_urls: list[str] = Field(description="Most relevant URLs found")

class EmailOutput(BaseModel):
    subject_line: str
    email_body: str = Field(description="Full personalized cold email, 3 paragraphs max")
    personalization_hook: str = Field(description="The specific fact used to personalize this email")

# ── MCP server params ─────────────────────────────────────────────────────────
# Use sys.executable so the MCP subprocess uses the SAME venv Python as the backend
MCP_SERVER = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).parent / "mcp_server.py")],
    env=None,
)

def _safe_dump(task, fallback: dict) -> dict:
    """Return pydantic output if available, otherwise return fallback."""
    try:
        return task.output.pydantic.model_dump()
    except Exception:
        return fallback

def run_crew(company: str, target_role: str, your_offering: str) -> dict:
    """Run the full 3-agent crew and return structured JSON."""
    with MCPServerAdapter(MCP_SERVER) as mcp_tools:

        researcher = Agent(
            role="Technical Research Specialist",
            goal=f"Find technical information, news, and engineering challenges about {company} relevant to a {target_role}.",
            backstory=f"You are a technical researcher. You search for engineering blogs, technical challenges, and news related to the '{target_role}' department. You look for organic, real-world problems they are facing. If you cannot find highly specific technical information, you still provide the best available technical or company context, rather than returning nothing.",
            tools=mcp_tools,
            llm=LLM,
            verbose=True,
            allow_delegation=False,
        )

        analyst = Agent(
            role="Sales Analyst",
            goal=f"Extract a real-world, factual constraint or challenge a {target_role} at {company} is currently facing, based ONLY on the provided research.",
            backstory="You are a sharp B2B sales strategist. You analyze research data to find a real, tangible problem the prospect is having. You NEVER use circular logic (e.g., if the user's offering is 'SEO services', you don't say the pain point is 'they need SEO services' — you say 'their recent blog posts aren't ranking on page 1'). You find the underlying factual constraint.",
            llm=LLM,
            verbose=True,
            allow_delegation=False,
        )

        writer = Agent(
            role="Cold Email Copywriter",
            goal=f"Write a hyper-personalized, 3-paragraph cold email pitching: {your_offering}.",
            backstory="You write cold emails that feel like they were written by a founder who did their homework, not a spam bot. Short, direct, specific.",
            llm=LLM,
            verbose=True,
            allow_delegation=False,
        )

        research_task = Task(
            description=(
                f"Research the company '{company}'. Use web_search to find information relevant to '{target_role}'.\n\n"
                f"RULES:\n"
                f"1. Prioritize specific news, blog posts, and challenges relevant to '{target_role}'. Use search queries like '{company} {target_role} challenges' or '{company} engineering blog'.\n"
                f"2. If you find highly relevant technical URLs, use the read_page tool to extract details.\n"
                f"3. CRITICAL: You must NEVER leave the output arrays empty. If you cannot find perfectly niche information, populate the arrays with the closest relevant technical or company context you found."
            ),
            expected_output=(
                "A JSON object with keys: company_name, recent_news (list), "
                "tech_stack (list), pain_points (list), key_urls (list)."
            ),
            output_pydantic=ResearchOutput,
            agent=researcher,
        )

        analyst_task = Task(
            description=(
                f"Based strictly on the research gathered, identify the single most painful, factual problem a '{target_role}' "
                f"at '{company}' is likely facing right now. \n"
                f"CRITICAL RULE: Do NOT just parrot back the offering ('{your_offering}') as the pain point. "
                f"For example, if the offering is 'AWS cost reduction', the pain point is 'high compute costs for recent model training', NOT 'need for AWS cost reduction'. "
                f"Find the actual symptom/constraint from the research."
            ),
            expected_output="A concise analysis of the key pain point, distinct from the offering itself.",
            agent=analyst,
            context=[research_task],
        )

        write_task = Task(
            description=(
                f"Write a personalized cold email pitching '{your_offering}' to the '{target_role}' at '{company}'. "
                f"Use the analyst's pain point as the hook. Keep it to 3 short paragraphs. "
                f"No generic opener like 'I hope this finds you well.' "
                f"Return a JSON object with keys: subject_line, email_body, personalization_hook."
            ),
            expected_output="A JSON object with subject_line, email_body, and personalization_hook.",
            output_pydantic=EmailOutput,
            agent=writer,
            context=[research_task, analyst_task],
        )

        crew = Crew(
            agents=[researcher, analyst, writer],
            tasks=[research_task, analyst_task, write_task],
            process=Process.sequential,
            verbose=True,
            cache=False,  # Disable CrewAI internal cache to avoid injecting weird params
        )

        crew.kickoff()

        research_data = _safe_dump(research_task, {
            "company_name": company,
            "recent_news": ["Could not retrieve research data."],
            "tech_stack": [],
            "pain_points": [],
            "key_urls": [],
        })
        email_data = _safe_dump(write_task, {
            "subject_line": "Following up",
            "email_body": str(write_task.output.raw) if write_task.output else "No email generated.",
            "personalization_hook": "N/A",
        })

        return {"research": research_data, "email": email_data}
