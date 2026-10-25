"""Shortlist and sent offers: a small server-side record (JSON files next to the other artifacts)."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api import artifacts

router = APIRouter(tags=["actions"])
_lock = threading.Lock()


def _path(name: str):
    return artifacts.artifacts_dir() / name


def _read(name: str) -> list:
    p = _path(name)
    return json.loads(p.read_text()) if p.exists() else []


def _known(customer_id: str) -> bool:
    return bool((artifacts.people()["customer_id"] == customer_id).any())


class SendRequest(BaseModel):
    customer_id: str
    offer: str | None = Field(None, max_length=64)


@router.get("/shortlist")
def get_shortlist():
    return {"customer_ids": _read("shortlist.json")}


@router.put("/shortlist/{customer_id}")
def add_to_shortlist(customer_id: str):
    if not _known(customer_id):
        raise HTTPException(404, f"Unknown customer {customer_id}")
    with _lock:
        ids = _read("shortlist.json")
        if customer_id not in ids:
            ids.append(customer_id)
            _path("shortlist.json").write_text(json.dumps(ids))
    return {"customer_ids": ids}


@router.delete("/shortlist/{customer_id}")
def remove_from_shortlist(customer_id: str):
    with _lock:
        ids = [i for i in _read("shortlist.json") if i != customer_id]
        _path("shortlist.json").write_text(json.dumps(ids))
    return {"customer_ids": ids}


@router.post("/offers/send")
def send_offer(req: SendRequest):
    """Record that an offer was sent. Nothing is delivered: this is the audit log the team would act on."""
    if not _known(req.customer_id):
        raise HTTPException(404, f"Unknown customer {req.customer_id}")
    entry = {"customer_id": req.customer_id, "offer": req.offer,
             "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with _lock:
        log = _read("offers_sent.json")
        log.append(entry)
        _path("offers_sent.json").write_text(json.dumps(log))
    return entry


@router.get("/offers/sent")
def sent_offers():
    return {"items": list(reversed(_read("offers_sent.json")))}
