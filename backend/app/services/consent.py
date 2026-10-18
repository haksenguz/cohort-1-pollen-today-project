"""민감정보 consent: the record, the text, and the state it puts the app in.

Why this exists. The app stores and transmits 건강 information — allergy
profiles, symptom descriptions, breathing-difficulty answers. Under
개인정보 보호법 제23조① that is 민감정보, and it may only be processed where the
subject has given **separate** consent, informed of the four items 제15조② lists.
제15조 requires that consent to be distinguishable from consent to anything else,
which is why this is not a boolean on the account but its own columns with their
own version.

What was actually missing before this module: nothing recorded the consent at
all. `privacy.py` described health data as 민감정보 and then processed it.

The disclosure that matters most, and the one that was absent everywhere else in
the product: **symptom text is sent to the LLM provider.** The conversation the
user typed is shipped to an external API (`core/openai_client.py`) to be answered.
That is 위탁 under 제22조, it involves 민감정보, and the privacy summary used to
mention only where the *saved coordinates* do not go. Silence about the one that
actually does leave the server is worse than saying it.

The policy text below is a **draft**. It states what the code does, sectioned as
제30조 requires, and it is served with `requires_legal_review: true` rather than
presented as a finished legal document. Someone qualified has to sign off on it
before this goes in front of a real user — that call is not an engineer's and
this module does not pretend otherwise.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

# Bump when POLICY text changes in substance. Stored per user so "which text did
# they agree to" stays answerable after the text moves on.
POLICY_VERSION = "2026-10-19-draft1"

SENSITIVE_PURPOSE = "health_data_processing"

# 제15조② requires these four be disclosed before 민감정보 consent is requested.
REQUIRED_NOTICE_ITEMS = (
    "수집·이용 목적",
    "수집하는 민감정보의 항목",
    "보유 및 이용 기간",
    "동의를 거부할 권리와 거부 시 불이익",
)

POLICY: dict[str, Any] = {
    "title": "개인정보 처리방침 (초안)",
    "version": POLICY_VERSION,
    "status": "draft",
    "requires_legal_review": True,
    "effective_from": None,
    "operator": "allergy-ai (개인정보처리자 — 사업자 정보는 배포 전에 채워야 합니다)",
    "sections": [
        {
            "heading": "1. 개인정보의 처리 목적",
            "body": [
                "이 앱은 알레르기·꽃가루 관련 증상 질문에 답하기 위해 개인정보를 처리합니다.",
                "구체적으로는 (1) 사용자가 입력한 증상을 구조화해 규칙 기반 판단에 전달하고, "
                "(2) 사용자가 요청할 때 가까운 알레르기진료 기관을 찾아주고, "
                "(3) 꽃가루·대기질 수치와 사용자의 알레르기 정보를 비교해 알림을 제공합니다.",
                "이 앱은 진단하거나 치료를 권하지 않습니다.",
            ],
        },
        {
            "heading": "2. 수집하는 개인정보 항목",
            "body": [
                "일반 개인정보: 이메일 주소, 비밀번호(해시값), 저장된 위치 좌표, 기관 검색 기록.",
                "민감정보(제23조, 건강에 관한 정보): 알레르기 종류와 중증도, "
                "채팅으로 입력한 내용, 증상·심각도·지속시간·추정 원인, "
                "호흡 곤란 여부와 기도부종 여부, 규칙 엔진이 판정한 위험 수준과 그 사유.",
                "수집하지 않는 것: 이름, 나이, 성별, 주소, 주민등록번호, "
                "임의의 사진·음성·기기 위치 기록.",
            ],
        },
        {
            "heading": "3. 민감정보의 처리 위탁 (제22조)",
            "body": [
                "사용자가 채팅에 입력한 내용은 답변을 생성하기 위해 외부 언어모델 "
                "제공업체의 API로 전송됩니다. 이 과정에서 건강에 관한 민감정보가 "
                "전송될 수 있습니다.",
                "전송 목적: 대화 응답 생성 및 증상 정보 구조화.",
                "전송 범위: 대화 내용과 시스템 지시문. 저장된 위치 좌표는 "
                "언어모델에 전송하지 않습니다.",
                "제공업체: 배포 시 운영자가 특정해야 합니다. "
                "이용 대가는 제공업체의 정책에 따릅니다.",
            ],
        },
        {
            "heading": "4. 보유 및 이용 기간",
            "body": [
                "계정이 존재하는 동안 보유합니다.",
                "사용자가 직접 삭제하면 해당 데이터는 즉시 영구 삭제되며 복구할 수 없습니다.",
            ],
        },
        {
            "heading": "5. 개인정보의 파기절차 및 파기방법",
            "body": [
                "계정 삭제 시 관련 데이터베이스 레코드를 물리적으로 삭제합니다. "
                "복구 수단(소프트 삭제, 백업 보존)은 두지 않습니다.",
                "삭제 대상: 대화와 메시지, 증상 이벤트, 판정 결과, 알레르기 목록, "
                "기관 검색 기록, 알림, 알림 설정, 민감정보 동의 기록.",
                "위치별 공기질·꽃가루 관측값은 개인을 식별하지 않고 위치 기준으로 "
                "공유 캐시되므로, 한 계정의 삭제로 제거되지 않습니다.",
            ],
        },
        {
            "heading": "6. 민감정보의 공개 가능성 및 비공개 선택 방법 (제23조③)",
            "body": [
                "이 앱은 사용자의 민감정보를 제3자에게 공개하는 기능(게시, 공유 링크 생성)을 "
                "제공하지 않습니다.",
                "민감정보가 외부로 전송되는 유일한 경우는 3항에 적은 언어모델 제공업체로의 "
                "응답 생성이며, 이는 사용자가 대화를 시작하는 행위 자체에 포함됩니다.",
                "사용자는 언제든지 민감정보 처리에 대한 동의를 철회할 수 있고, 철회 후에는 "
                "대화를 시작할 수 없습니다.",
            ],
        },
        {
            "heading": "7. 정보주체의 권리 (제35조, 제36조)",
            "body": [
                "열람·전송: 앱 안에서 전체 데이터를 파일로 내려받을 수 있습니다.",
                "정정·삭제: 계정 삭제를 통해 처리됩니다.",
                "제38조④에 따라 열람과 삭제는 가입할 때와 같은 수준의 노력으로 이루어집니다.",
            ],
        },
    ],
}


def _now() -> datetime:
    return datetime.now(UTC)


async def record_sensitive_consent(
    session: AsyncSession,
    *,
    user: User,
    granted: bool,
    version: str | None = None,
) -> User:
    """Record or withdraw 민감정보 consent. The caller commits.

    Withdrawing clears `sensitive_consent_at` rather than leaving it alone and
    setting a withdrawn timestamp. Two reasons: a withdrawn user must not look
    consented to any code that checks the consent column alone, and keeping a
    "granted at" that no longer means anything is how a withdrawn record ends up
    being cited as evidence of consent.

    The withdrawn timestamp is kept, because "when did they withdraw" is
    answerable and "did we act after they withdrew" is checkable.
    """
    stamp = _now()
    if granted:
        user.sensitive_consent_at = stamp
        user.sensitive_consent_version = version or POLICY_VERSION
        user.sensitive_consent_withdrawn_at = None
    else:
        user.sensitive_consent_at = None
        user.sensitive_consent_version = None
        user.sensitive_consent_withdrawn_at = stamp
    session.add(user)
    await session.flush()
    return user


def consent_state(user: User) -> dict[str, Any]:
    """Current consent, in the shape the API and the frontend both consume."""
    granted = user.sensitive_consent_at is not None
    return {
        "purpose": SENSITIVE_PURPOSE,
        "granted": granted,
        "version": user.sensitive_consent_version,
        "granted_at": user.sensitive_consent_at.isoformat() if user.sensitive_consent_at else None,
        "withdrawn_at": user.sensitive_consent_withdrawn_at.isoformat()
        if user.sensitive_consent_withdrawn_at
        else None,
        "policy_version": POLICY_VERSION,
        "basis": "개인정보 보호법 제23조제1항제1호, 제15조제2항",
    }


def has_sensitive_consent(user: User) -> bool:
    """True when 민감정보 may currently be processed for this user.

    Not enforced on the write paths yet — see the open item in bugs.md. Enforcing
    it partially would gate some writes and not others, which is worse than
    gating none: it produces an app that half-works and a support question with
    no good answer.
    """
    return user.sensitive_consent_at is not None
