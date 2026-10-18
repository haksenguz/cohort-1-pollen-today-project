"""Personal-data endpoints (개인정보 보호법 제4조 / 제35조 / 제36조).

Design constraint that shapes all of it: **제38조④ requires that asking for
access or deletion be no harder than signing up was.** Sign-up is one form.
So all three rights live behind the same bearer token the user already has, in
one router, with no email round-trip, no support ticket, and no identity
check beyond the session that is already open. Putting these behind a mail
request would satisfy the law's letter and fail its intent.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.services import consent as consent_service
from app.services import privacy_service

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


class ConsentRequest(BaseModel):
    """Grant or withdraw 민감정보 consent (제23조①1호)."""

    granted: bool
    version: str | None = Field(
        default=None,
        max_length=32,
        description="Policy version agreed to. Defaults to the current one.",
    )


class ConsentResponse(BaseModel):
    purpose: str
    granted: bool
    version: str | None
    granted_at: str | None
    withdrawn_at: str | None
    policy_version: str
    basis: str


@router.get("/policy")
async def privacy_policy() -> dict[str, Any]:
    """The 개인정보 처리방침 itself (제30조 requires that it be published).

    Public and unauthenticated on purpose: a policy a user can only see after
    signing in was not disclosed before consent was sought, which is the whole
    point of 제15조②.

    Served as data rather than a rendered page so there is one source of truth
    and the frontend can present it in whatever shape its locale needs.
    """
    return {
        **consent_service.POLICY,
        "required_notice_items": list(consent_service.REQUIRED_NOTICE_ITEMS),
    }


@router.get("/consent")
async def get_consent(current_user: CurrentUser) -> ConsentResponse:
    """What the signed-in user has agreed to, if anything."""
    return ConsentResponse(**consent_service.consent_state(current_user))


@router.post("/consent")
async def set_consent(
    body: ConsentRequest, session: SessionDep, current_user: CurrentUser
) -> ConsentResponse:
    """Record or withdraw 민감정보 consent."""
    user = await consent_service.record_sensitive_consent(
        session, user=current_user, granted=body.granted, version=body.version
    )
    await session.commit()
    return ConsentResponse(**consent_service.consent_state(user))


class StoredDataPoint(BaseModel):
    """One category of personal data, and where it lives."""

    what: str
    table: str
    sensitive: bool = False
    note: str | None = None


class PrivacySummary(BaseModel):
    """What is held, so the user can see it before asking for a copy."""

    account_email: str
    generated_at: str
    sensitive_consent: ConsentResponse
    data_points: list[StoredDataPoint]
    not_stored: list[str] = Field(
        default_factory=list,
        description=(
            "Things deliberately not collected. Stating these matters as much as "
            "stating what is held: silence reads as a gap in the policy."
        ),
    )


# Health data is 민감정보 under 제23조 and needs its own consent, so every row
# derived from what a user typed about their body is marked. Location is not
# sensitive on its own but is personal data and is retained indefinitely as
# search history, which is why it is called out in the note.
_SUMMARY_POINTS: list[StoredDataPoint] = [
    StoredDataPoint(
        what="Account: email, password hash, optional saved location",
        table="users",
        note=(
            "Your saved coordinates are used to search for nearby clinics. They are "
            "never sent to the LLM and never placed in a prompt."
        ),
    ),
    StoredDataPoint(
        what="Your allergies and how severe you rated each",
        table="user_allergies",
        sensitive=True,
    ),
    StoredDataPoint(
        what="Everything you typed in the chat, and every reply the app gave",
        table="conversations, messages",
        sensitive=True,
        note=(
            "Retained for the life of the account. Deleting the account removes all of it. "
            "This text is the one thing that leaves the server: it is sent to the LLM "
            "provider to generate an answer (see the policy's section 3)."
        ),
    ),
    StoredDataPoint(
        what=(
            "Extracted symptoms, severity, duration, suspected trigger, and whether "
            "you reported breathing difficulty or airway swelling"
        ),
        table="symptom_events",
        sensitive=True,
    ),
    StoredDataPoint(
        what="The risk level the rule engine assigned, with its reasons and version",
        table="triage_results",
        sensitive=True,
        note=(
            "Computed by a deterministic rule engine, not by the model. The model cannot change it."
        ),
    ),
    StoredDataPoint(
        what="Where and when you searched for nearby clinics, and which results came back",
        table="hospital_searches, hospital_results",
        note="Retains precise coordinates as search history.",
    ),
    StoredDataPoint(
        what="Alerts raised from your readings",
        table="alerts",
        sensitive=True,
    ),
    StoredDataPoint(
        what="Which alert types you switched on, and quiet hours",
        table="notification_preferences",
    ),
]


@router.get("/summary")
async def privacy_summary(current_user: CurrentUser) -> PrivacySummary:
    """What is held about the signed-in user (제4조1, 제30조)."""
    return PrivacySummary(
        account_email=current_user.email,
        generated_at=datetime.now().astimezone().isoformat(),
        sensitive_consent=ConsentResponse(**consent_service.consent_state(current_user)),
        data_points=_SUMMARY_POINTS,
        not_stored=[
            "Your name, age, gender, address or national identifier — never collected.",
            "Your name, address or phone number at any clinic — never asked for.",
            "Any photo, audio or location history from your device — never accessed.",
            "Advertising or analytics identifiers — there is no third-party tracker in this app.",
            (
                "Any public posting or share link for your health data — the app has no "
                "such feature, which is what keeps 제23조③ satisfied."
            ),
        ],
    )


@router.get("/export")
async def export_my_data(session: SessionDep, current_user: CurrentUser) -> Response:
    """A complete copy of everything held about the signed-in user.

    Sent as a file download rather than rendered in the app, because this is a
    *transmission* right: the user is entitled to a copy they can keep, not a
    page that happens to display one.
    """
    document = await privacy_service.export_user_data(session, user_id=current_user.id)
    body = json.dumps(document, ensure_ascii=False, indent=2, default=str)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="my-data-{stamp}.json"',
            # Personal data must not sit in a shared cache.
            "Cache-Control": "no-store",
        },
    )


class DeletionReceipt(BaseModel):
    deleted: dict[str, int]
    note: str


@router.delete("/account")
async def delete_my_account(session: SessionDep, current_user: CurrentUser) -> DeletionReceipt:
    """Delete the account and every row belonging to it (제36조).

    Hard delete, not a flag. 제36조③ requires that deletion leave nothing that
    can be recovered or regenerated, so there is no soft-delete column to set
    and nothing is left to find later.
    """
    removed = await privacy_service.delete_user_account(session, user_id=current_user.id)
    # One commit for the whole account. A partial delete is the worst outcome:
    # the user is told their data is gone while some of it still exists.
    await session.commit()
    return DeletionReceipt(
        deleted=removed,
        note=(
            "Permanently deleted. This cannot be undone and there is no recovery "
            "period - health data held on this account is gone."
        ),
    )


@router.get("/health-note", response_class=JSONResponse)
async def health_data_note() -> dict[str, Any]:
    """Plain statement that the symptom data is sensitive data (제23조).

    Left unauthenticated, as it was: it states facts about the service rather
    than about a person, and a page a user reads *before* signing in is the one
    that can actually inform consent. Per-user consent state lives on /summary,
    which is authenticated.
    """
    return {
        "sensitive_data_categories": ["health", "location"],
        "basis": "개인정보 보호법 제23조 (민감정보)",
        "policy_url": "/api/privacy/policy",
        "third_party_transfer": {
            "sent": ["chat content", "symptoms described in chat"],
            "not_sent": ["saved location coordinates", "email", "password"],
            "to": "the configured LLM provider (OPENAI_BASE_URL)",
            "why": "the answer has to be generated by the model, which runs off-device",
            "basis": "개인정보 보호법 제22조 (위탁) — disclosure required in the policy",
        },
        "note": (
            "Symptom and triage data is health information and is treated as "
            "sensitive data. It is processed to answer the user's question and is "
            "never used for advertising or profiling."
        ),
    }
