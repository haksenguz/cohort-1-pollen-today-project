"""The policy names the operator, or says plainly that nobody is named yet.

제30조 wants a 사업자 and a 사업자등록번호 in the privacy policy. The text used
to carry a placeholder that read like a real name, which is the one thing a
policy cannot do: a reader would take it for the operator.

The operator now comes from the environment. When the environment says
nothing, the policy says that too, in plain words, rather than pretending it
is publishable.
"""

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.services import consent as consent_service


@pytest.fixture
def named_operator(monkeypatch):
    settings = Settings(
        operator_name="Pollen Health Co.",
        operator_registration_number="123-45-67890",
    )
    monkeypatch.setattr(consent_service, "get_settings", lambda: settings)
    return settings


@pytest.fixture
def unnamed_operator(monkeypatch):
    settings = Settings(operator_name="", operator_registration_number="")
    monkeypatch.setattr(consent_service, "get_settings", lambda: settings)
    return settings


def _first_section_text(document: dict) -> str:
    return " ".join(document["sections"][0]["body"])


def test_the_policy_names_the_operator_when_the_settings_carry_it(named_operator) -> None:
    document = consent_service.policy_document()

    assert document["operator_named"] is True
    assert document["operator_name"] == "Pollen Health Co."
    assert document["operator_registration_number"] == "123-45-67890"
    assert "Pollen Health Co." in document["operator"]
    assert "123-45-67890" in document["operator"]

    body = _first_section_text(document)
    assert "Pollen Health Co." in body
    assert "123-45-67890" in body


def test_the_policy_says_it_cannot_be_published_when_no_operator_is_named(
    unnamed_operator,
) -> None:
    document = consent_service.policy_document()

    assert document["operator_named"] is False
    assert document["operator_name"] is None
    assert document["operator_registration_number"] is None

    body = _first_section_text(document)
    assert "아직 정해지지 않았습니다" in body
    assert "공개할 수 없습니다" in body


def test_the_policy_never_claims_to_be_publishable_on_its_own() -> None:
    """A human decides that, not the code.

    `requires_legal_review` stays true whatever the operator settings say, so
    an operator name cannot make the policy look finished.
    """
    document = consent_service.policy_document()

    assert document["requires_legal_review"] is True
    assert document["status"] == "draft"


@pytest.mark.asyncio
async def test_the_policy_endpoint_serves_the_operator(client: AsyncClient) -> None:
    res = await client.get("/api/privacy/policy")

    assert res.status_code == 200
    body = res.json()
    assert "operator_named" in body
    assert body["required_notice_items"], "the four 제15조② items have to travel with it"
