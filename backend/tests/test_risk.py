from app.core.enums import PollenLevel, RiskLevel
from app.services import risk


def test_clean_air_is_low():
    _pts, level = risk.score(risk.EnvInput(tree_pollen=PollenLevel.LOW, pm25=5))
    assert level is RiskLevel.LOW


def test_high_pollen_and_pm25_is_moderate_or_high():
    pts, level = risk.score(risk.EnvInput(tree_pollen=PollenLevel.HIGH, pm25=42, wind_speed=4.2))
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


def test_a_sampled_pollen_level_scores_nothing():
    """The unkeyed sample is a hardcoded placeholder, not a reading.

    Scoring it as HIGH told the user "moderate" on the strength of a number
    the note right below it said was being withheld.
    """
    sampled = risk.EnvInput(tree_pollen=PollenLevel.HIGH, pollen_is_sample=True)
    measured = risk.EnvInput(tree_pollen=PollenLevel.HIGH)
    pts, level = risk.score(sampled)
    assert pts == 0
    assert level is RiskLevel.LOW
    assert risk.score(measured)[0] > pts


def test_a_sampled_pollen_level_does_not_boost_a_known_allergen():
    sampled = risk.EnvInput(tree_pollen=PollenLevel.HIGH, pollen_is_sample=True)
    assert risk.score(sampled, user_allergens={"TREE_POLLEN"})[0] == 0


def test_real_data_is_still_scored_when_the_pollen_is_a_sample():
    """The air and the weather are measurements even when the pollen is not."""
    env = risk.EnvInput(pm25=42, wind_speed=6, pollen_is_sample=True)
    pts, level = risk.score(env)
    assert pts >= 3
    assert level in (RiskLevel.MODERATE, RiskLevel.HIGH)


def test_has_data_is_false_when_nothing_answered():
    """Every provider down gives a score of zero points, which is LOW.

    That reads as "you are fine today" on a day the app could not ask anybody,
    so the caller has to be able to tell the two apart.
    """
    assert risk.has_data(risk.EnvInput()) is False
    assert (
        risk.has_data(risk.EnvInput(tree_pollen=PollenLevel.HIGH, pollen_is_sample=True)) is False
    )


def test_has_data_is_true_for_any_real_measurement():
    assert risk.has_data(risk.EnvInput(pm25=5)) is True
    assert risk.has_data(risk.EnvInput(tree_pollen=PollenLevel.LOW)) is True
    assert risk.has_data(risk.EnvInput(wind_speed=2)) is True
