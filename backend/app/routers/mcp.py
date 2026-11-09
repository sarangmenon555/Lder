import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, CheckIn, Elder
from ..security import verify_scoped_token
from ..services import checkins as checkin_service
from ..timeutil import format_local

router = APIRouter(tags=["mcp"])

SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "lder-checkins", "version": "1.0.0"}

TOOLS = [
    {
        "name": "get_profile",
        "description": "Basic profile of the person: name, language, time zone, check-in times and medicine schedule.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_recent_checkins",
        "description": "Most recent check-ins with status, mood, medicine report and a short summary. Newest first.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 10}},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_summary",
        "description": "Statistics for the last N days: response rate, medicine adherence, mood mix, alert counts.",
        "inputSchema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7}},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_alerts",
        "description": "Recent alerts for this person with severity, reason, time and whether it was acknowledged.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 10}},
            "additionalProperties": False,
        },
    },
]

TOOL_NAMES = [tool["name"] for tool in TOOLS]


def _int_arg(arguments: dict, name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(arguments.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value))


def run_tool(db: Session, elder: Elder, name: str, arguments: dict) -> dict:
    if name == "get_profile":
        return {
            "name": elder.name,
            "language": elder.language,
            "timezone": elder.timezone,
            "check_in_times": elder.check_in_times,
            "active": elder.active,
            "medicines": [{"name": m.name, "time_of_day": m.time_of_day} for m in elder.medicines],
        }
    if name == "get_recent_checkins":
        limit = _int_arg(arguments, "limit", 10, 1, 30)
        rows = db.scalars(
            select(CheckIn).where(CheckIn.elder_id == elder.id).order_by(CheckIn.scheduled_at.desc()).limit(limit)
        ).all()
        return {
            "checkins": [
                {
                    "time": format_local(row.responded_at or row.scheduled_at, elder.timezone),
                    "kind": row.kind,
                    "status": row.status,
                    "classification": row.classification,
                    "medicine_taken": row.medicine_taken,
                    "mood": row.mood,
                    "summary": row.summary,
                }
                for row in rows
            ]
        }
    if name == "get_summary":
        days = _int_arg(arguments, "days", 7, 1, 30)
        stats = checkin_service.build_summary(db, elder, days)
        return {key: stats[key] for key in stats if key != "recent_summaries"}
    if name == "get_alerts":
        limit = _int_arg(arguments, "limit", 10, 1, 30)
        rows = db.scalars(
            select(Alert).where(Alert.elder_id == elder.id).order_by(Alert.sent_at.desc()).limit(limit)
        ).all()
        return {
            "alerts": [
                {
                    "time": format_local(row.sent_at, elder.timezone),
                    "severity": row.severity,
                    "reason": row.reason,
                    "acknowledged": row.acknowledged_at is not None,
                }
                for row in rows
            ]
        }
    raise KeyError(name)


def _result(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(db: Session, elder: Elder, message: dict) -> dict | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid request")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if request_id is None:
        return None
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return _result(
            request_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        )
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOL_NAMES or not isinstance(arguments, dict):
            return _error(request_id, -32602, "Unknown tool or invalid arguments")
        data = run_tool(db, elder, name, arguments)
        return _result(
            request_id,
            {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}], "isError": False},
        )
    return _error(request_id, -32601, "Method not found")


def _elder_from_header(db: Session, authorization: str | None) -> Elder:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    elder_id = verify_scoped_token(authorization[7:])
    if elder_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    elder = db.get(Elder, elder_id)
    if elder is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return elder


@router.post("/mcp")
async def mcp_endpoint(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    elder = _elder_from_header(db, authorization)
    try:
        body = await request.json()
    except ValueError:
        return Response(
            content=json.dumps(_error(None, -32700, "Parse error")),
            media_type="application/json",
            status_code=400,
        )
    if isinstance(body, list):
        replies = [reply for reply in (handle_message(db, elder, item) for item in body) if reply is not None]
        if not replies:
            return Response(status_code=202)
        return Response(content=json.dumps(replies, ensure_ascii=False), media_type="application/json")
    reply = handle_message(db, elder, body)
    if reply is None:
        return Response(status_code=202)
    return Response(content=json.dumps(reply, ensure_ascii=False), media_type="application/json")


@router.get("/mcp")
def mcp_get():
    return Response(status_code=405, headers={"Allow": "POST"})
