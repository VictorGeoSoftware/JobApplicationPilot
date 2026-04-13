from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import DOCS_DIR, QUESTIONS_PATH, ROOT_DIR, settings
from app.models import JobSeekerRequest, JobSeekerResponse, RecruiterRequest, RecruiterResponse
from app.services.context_store import ContextStore
from app.services.job_seeker_agent import JobSeekerAgent
from app.services.llm_factory import build_llm_client
from app.services.llm_client import MissingConfigError, UpstreamModelError
from app.services.question_log import QuestionLogger
from app.services.recruiter_agent import RecruiterAgent
from app.services.web_search import WebSearchService


@asynccontextmanager
async def lifespan(app: FastAPI):
    context_store = ContextStore(DOCS_DIR)
    question_logger = QuestionLogger(QUESTIONS_PATH, max_logs=settings.max_question_logs)
    web_search = WebSearchService()
    llm_client = build_llm_client()

    app.state.context_store = context_store
    app.state.question_logger = question_logger
    app.state.recruiter_agent = RecruiterAgent(context_store, web_search, llm_client)
    app.state.job_seeker_agent = JobSeekerAgent(llm_client, web_search, ROOT_DIR.parent)
    yield


app = FastAPI(title="Elite Technical Recruiter API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "provider": settings.llm_provider,
        "model": app.state.recruiter_agent.llm_client.model,
        "docs_dir": str(DOCS_DIR),
    }


@app.post("/api/recruiter/answer", response_model=RecruiterResponse)
async def recruiter_answer(payload: RecruiterRequest) -> RecruiterResponse:
    app.state.question_logger.save(payload.question)

    try:
        answer, context_files, web_research = await app.state.recruiter_agent.answer(payload)
    except MissingConfigError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except UpstreamModelError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Model request failed: {error}") from error

    return RecruiterResponse(
        answer=answer,
        used_context_files=context_files,
        web_research=web_research,
    )


@app.post("/api/jobseeker/run", response_model=JobSeekerResponse)
async def run_jobseeker(_payload: JobSeekerRequest) -> JobSeekerResponse:
    try:
        result = await app.state.job_seeker_agent.run()
    except MissingConfigError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except UpstreamModelError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"JobSeeker run failed: {error}") from error

    return JobSeekerResponse(**result)
