"""
Unit tests for Pydantic request/response schemas.

Pure logic — no database or network required.
"""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.event import EventIngest, EventIngestResponse


VALID_PAYLOAD = {
    "batch_id": str(uuid.uuid4()),
    "station_id": str(uuid.uuid4()),
    "event_type": "completed",
    "device_id": "device_android_001",
    "idempotency_key": str(uuid.uuid4()),
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "metadata": {},
}


# ── EventIngest ────────────────────────────────────────────────────────────────


def test_event_ingest_valid_types():
    for event_type in ("started", "completed", "issue_flagged", "skipped"):
        payload = {**VALID_PAYLOAD, "event_type": event_type}
        model = EventIngest.model_validate(payload)
        assert model.event_type == event_type


def test_event_ingest_rejects_invalid_type():
    with pytest.raises(ValidationError) as exc_info:
        EventIngest.model_validate({**VALID_PAYLOAD, "event_type": "destroyed"})
    assert "event_type" in str(exc_info.value)


def test_event_ingest_requires_batch_id():
    data = {k: v for k, v in VALID_PAYLOAD.items() if k != "batch_id"}
    with pytest.raises(ValidationError):
        EventIngest.model_validate(data)


def test_event_ingest_requires_idempotency_key():
    data = {k: v for k, v in VALID_PAYLOAD.items() if k != "idempotency_key"}
    with pytest.raises(ValidationError):
        EventIngest.model_validate(data)


def test_event_ingest_idempotency_key_is_uuid():
    with pytest.raises(ValidationError):
        EventIngest.model_validate({**VALID_PAYLOAD, "idempotency_key": "not-a-uuid"})


def test_event_ingest_metadata_defaults_to_empty_dict():
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "metadata"}
    model = EventIngest.model_validate(payload)
    assert model.metadata == {}


def test_event_ingest_metadata_accepts_nested():
    payload = {**VALID_PAYLOAD, "metadata": {"asr_confidence": 0.94, "source": "voice"}}
    model = EventIngest.model_validate(payload)
    assert model.metadata["asr_confidence"] == 0.94


def test_event_ingest_timestamp_parsed_to_datetime():
    model = EventIngest.model_validate(VALID_PAYLOAD)
    assert isinstance(model.timestamp, datetime)


# ── EventIngestResponse ────────────────────────────────────────────────────────


def test_response_defaults_queued_true():
    event_id = uuid.uuid4()
    resp = EventIngestResponse(event_id=event_id)
    assert resp.queued is True
    assert resp.event_id == event_id


def test_response_queued_false_on_fallback():
    resp = EventIngestResponse(event_id=uuid.uuid4(), queued=False)
    assert resp.queued is False


# ── event_processor build helpers ─────────────────────────────────────────────


def test_build_event_from_request_sets_all_fields():
    from app.services.event_processor import build_event_from_request

    eid = uuid.uuid4()
    tid = uuid.uuid4()
    bid = uuid.uuid4()
    sid = uuid.uuid4()
    ikey = uuid.uuid4()
    ts = datetime.now(timezone.utc)

    event = build_event_from_request(
        event_id=eid,
        tenant_id=tid,
        batch_id=bid,
        station_id=sid,
        event_type="started",
        device_id="dev_001",
        idempotency_key=ikey,
        ts=ts,
        metadata={"source": "pwa"},
    )
    assert event.id == eid
    assert event.tenant_id == tid
    assert event.batch_id == bid
    assert event.station_id == sid
    assert event.event_type == "started"
    assert event.idempotency_key == ikey


def test_build_event_from_stream_parses_dict():
    import json
    from app.services.event_processor import build_event_from_stream

    eid = uuid.uuid4()
    data = {
        "event_id": str(eid),
        "tenant_id": str(uuid.uuid4()),
        "batch_id": str(uuid.uuid4()),
        "station_id": str(uuid.uuid4()),
        "event_type": "completed",
        "device_id": "dev_002",
        "idempotency_key": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": json.dumps({"asr_confidence": 0.88}),
    }
    event = build_event_from_stream(data)
    assert event.id == eid
    assert event.event_type == "completed"
    assert event.metadata_["asr_confidence"] == 0.88
