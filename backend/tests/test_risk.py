from app.core.enums import PollenLevel, RiskLevel
from app.services import risk


def test_clean_air_is_low():
    pts, level = risk.score(risk.EnvInput(tree_pollen=PollenLevel.LOW, pm25=5))
    assert level is RiskLevel.LOW


def test_high_pollen_and_pm25_is_moderate_or_high():
    pts, level = risk.score(
        risk.EnvInput(tree_pollen=PollenLevel.HIGH, pm25=42, wind_speed=4.2)
    )
    assert level in (RiskLevel.MODERATE, RiskLevel.HIGH)
    assert pts >= 3


def test_known_allergen_pushes_score_up():
    env = risk.EnvInput(tree_pollen=PollenLevel.HIGH, pm25=42, wind_speed=6)
    base, _ = risk.score(env)
    boosted, level = risk.score(env, user_allergens={"TREE_POLLEN"})
    assert boosted == base + 2
    assert level is RiskLevel.HIGH


def test_documentation_example_scores_high():
    # §14: pollen HIGH (+3) + known allergen (+2) ... reaches HIGH band
    env = risk.EnvInput(tree_pollen=PollenLevel.HIGH, pm25=42, wind_speed=6)
    pts, level = risk.score(env, user_allergens={"TREE_POLLEN"})
    assert pts >= 6
    assert level is RiskLevel.HIGH
