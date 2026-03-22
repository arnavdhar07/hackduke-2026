"""todos.py — Todo/task management for accepted recommendations."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app import database

router = APIRouter(prefix="/todos", tags=["todos"])

FARMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

class TodoResponse(BaseModel):
    id: uuid.UUID
    farmer_id: uuid.UUID
    field_id: uuid.UUID
    recommendation_id: uuid.UUID | None
    action_type: str
    zone_label: str
    field_name: str
    urgency: str
    status: str
    created_at: datetime
    completed_at: datetime | None

class TodoUpdate(BaseModel):
    status: str  # "done"

@router.get("", response_model=list[TodoResponse])
async def list_todos() -> list[TodoResponse]:
    pool = await database.get_pool()
    rows = await pool.fetch(
        "SELECT * FROM todos WHERE farmer_id = $1 ORDER BY created_at DESC",
        FARMER_ID,
    )
    return [TodoResponse(**dict(r)) for r in rows]

@router.patch("/{todo_id}", response_model=TodoResponse)
async def update_todo(todo_id: uuid.UUID, body: TodoUpdate) -> TodoResponse:
    pool = await database.get_pool()
    completed_at = datetime.now(tz=timezone.utc) if body.status == "done" else None
    row = await pool.fetchrow(
        """UPDATE todos SET status=$2, completed_at=$3 WHERE id=$1
           RETURNING *""",
        todo_id, body.status, completed_at,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return TodoResponse(**dict(row))
