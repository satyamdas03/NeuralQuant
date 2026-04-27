"""Team Hub — task tracking + agent standups for closed-loop operations.

Agents and human orchestrator coordinate through team_tasks and team_standups.
Uses direct httpx REST to PostgREST (same pattern as alerts.py).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from nq_api.auth import User, get_current_user

router = APIRouter(prefix="/team", tags=["team"])
log = logging.getLogger(__name__)

# ─── PostgREST helper ──────────────────────────────────────────────────────────

def _rest(
    table: str,
    method: str = "GET",
    query: dict[str, str] | None = None,
    body: Any = None,
) -> Any:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    endpoint = f"{url}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    try:
        with httpx.Client(timeout=10) as c:
            if method == "GET":
                r = c.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                r = c.post(endpoint, params=query or {}, json=body, headers=headers)
            elif method == "PATCH":
                r = c.patch(endpoint, params=query or {}, json=body, headers=headers)
            elif method == "DELETE":
                r = c.delete(endpoint, params=query or {}, headers=headers)
            else:
                raise HTTPException(status_code=500, detail=f"bad method {method}")
            r.raise_for_status()
            return {"data": r.json() if r.content else [], "headers": dict(r.headers)}
    except httpx.HTTPStatusError as exc:
        log.warning("PostgREST %s %s -> %s: %s", method, table, exc.response.status_code, exc.response.text[:200])
        raise HTTPException(status_code=502, detail=f"Supabase error: {exc.response.status_code}")
    except Exception as exc:
        log.exception("PostgREST %s %s failed", method, table)
        raise HTTPException(status_code=502, detail=f"Supabase request failed: {exc}")


# ─── Schemas ───────────────────────────────────────────────────────────────────

AgentRole = Literal[
    "NQ-Engineer", "NQ-Guardian", "NQ-Content", "NQ-Analyst-Ops",
    "NQ-Quant", "NQ-Biz", "NQ-Intel", "NQ-Support", "Satyam",
]

TaskStatus = Literal["pending", "in_progress", "in_review", "done", "blocked"]
TaskPriority = Literal["low", "medium", "high", "critical"]


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    assignee: AgentRole
    created_by: AgentRole = "Satyam"
    priority: TaskPriority = "medium"
    category: str = "general"
    reference_url: str | None = None


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    output: str | None = None
    review_notes: str | None = None
    assignee: AgentRole | None = None


class TaskOut(BaseModel):
    id: str
    title: str
    description: str | None
    assignee: str
    created_by: str
    status: str
    priority: str
    category: str
    output: str | None
    review_notes: str | None
    reference_url: str | None
    created_at: str
    updated_at: str


class TaskListResponse(BaseModel):
    items: list[TaskOut]
    count: int


class StandupCreate(BaseModel):
    agent_role: AgentRole
    summary: str = Field(..., min_length=1)
    blockers: str | None = None
    next_actions: str | None = None


class StandupOut(BaseModel):
    id: str
    agent_role: str
    summary: str
    blockers: str | None
    next_actions: str | None
    created_at: str


class StandupListResponse(BaseModel):
    items: list[StandupOut]
    count: int


# ─── Task endpoints ─────────────────────────────────────────────────────────────

@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    status: TaskStatus | None = Query(None),
    assignee: AgentRole | None = Query(None),
    priority: TaskPriority | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> TaskListResponse:
    """List team tasks, optionally filtered by status/assignee/priority."""
    query: dict[str, str] = {
        "select": "*",
        "order": "priority.asc,created_at.desc",
        "limit": str(limit),
    }
    if status:
        query["status"] = f"eq.{status}"
    if assignee:
        query["assignee"] = f"eq.{assignee}"
    if priority:
        query["priority"] = f"eq.{priority}"

    resp = _rest("team_tasks", method="GET", query=query)
    rows = resp["data"] or []
    items = [TaskOut(**r) for r in rows]
    return TaskListResponse(items=items, count=len(items))


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(req: TaskCreate, user: User = Depends(get_current_user)) -> TaskOut:
    """Create a new task. Agents or Satyam can assign work."""
    body = [req.model_dump(exclude_none=True)]
    resp = _rest("team_tasks", method="POST", body=body)
    rows = resp["data"] or []
    if not rows:
        raise HTTPException(status_code=500, detail="task creation failed")
    return TaskOut(**rows[0])


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    req: TaskUpdate,
    user: User = Depends(get_current_user),
) -> TaskOut:
    """Update task status, output, or review notes. Closed-loop: mark in_review for human review."""
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")
    resp = _rest(
        "team_tasks",
        method="PATCH",
        query={"id": f"eq.{task_id}"},
        body=updates,
    )
    rows = resp["data"] or []
    if not rows:
        raise HTTPException(status_code=404, detail="task not found")
    return TaskOut(**rows[0])


@router.get("/tasks/queue", response_model=TaskListResponse)
def review_queue(user: User = Depends(get_current_user)) -> TaskListResponse:
    """Get tasks awaiting human review (status=in_review)."""
    resp = _rest("team_tasks", method="GET", query={
        "select": "*",
        "status": "eq.in_review",
        "order": "priority.asc,created_at.asc",
    })
    rows = resp["data"] or []
    items = [TaskOut(**r) for r in rows]
    return TaskListResponse(items=items, count=len(items))


@router.get("/tasks/stats")
def task_stats(user: User = Depends(get_current_user)) -> dict:
    """Aggregate task counts by status and assignee."""
    resp = _rest("team_tasks", method="GET", query={"select": "status,assignee"})
    rows = resp["data"] or []
    by_status: dict[str, int] = {}
    by_assignee: dict[str, int] = {}
    for r in rows:
        s = r.get("status", "unknown")
        a = r.get("assignee", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        by_assignee[a] = by_assignee.get(a, 0) + 1
    return {"by_status": by_status, "by_assignee": by_assignee, "total": len(rows)}


# ─── Standup endpoints ──────────────────────────────────────────────────────────

@router.get("/standups", response_model=StandupListResponse)
def list_standups(
    agent_role: AgentRole | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
) -> StandupListResponse:
    """List agent standups, optionally filtered by agent role."""
    query: dict[str, str] = {
        "select": "*",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if agent_role:
        query["agent_role"] = f"eq.{agent_role}"
    resp = _rest("team_standups", method="GET", query=query)
    rows = resp["data"] or []
    items = [StandupOut(**r) for r in rows]
    return StandupListResponse(items=items, count=len(items))


@router.post("/standups", response_model=StandupOut, status_code=201)
def create_standup(req: StandupCreate, user: User = Depends(get_current_user)) -> StandupOut:
    """Agent posts a standup — what it did, blockers, next actions."""
    body = [req.model_dump(exclude_none=True)]
    resp = _rest("team_standups", method="POST", body=body)
    rows = resp["data"] or []
    if not rows:
        raise HTTPException(status_code=500, detail="standup creation failed")
    return StandupOut(**rows[0])