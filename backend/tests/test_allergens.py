"""The named-allergen catalogue (B-005).

Covers the three things the coarse-to-named switch could silently break:
every enum member resolves to a category, legacy coarse values still resolve,
and nothing gets silently swallowed as "no known allergen".
"""

import pytest

from app.core.enums import (
    ALLERGEN_CATEGORY,
    LEGACY_ALLERGENS,
    Allergen,
    AllergenCategory,
    allergen_category,
    resolve_allergen,
)


def test_every_allergen_resolves_to_a_category() -> None:
    missing = [a for a in Allergen if a not in ALLERGEN_CATEGORY]
    assert missing == [], f"allergens with no category: {missing}"


def test_every_allergen_fits_the_db_column() -> None:
    # user_allergies.allergen is VARCHAR(30) and is not widened by the DDL,
    # because the longest slug is far shorter. Guard it against a future member.
    too_long = [a.value for a in Allergen if len(a.value) > 30]
    assert too_long == [], f"allergen slugs that would be truncated: {too_long}"


@pytest.mark.parametrize(
    ("allergen", "expected"),
    [
        (Allergen.BIRCH, AllergenCategory.TREE),
        (Allergen.OAK, AllergenCategory.TREE),
        (Allergen.JAPANESE_CEDAR, AllergenCategory.TREE),
        (Allergen.TIMOTHY, AllergenCategory.GRASS),
        (Allergen.COCKSFOOT, AllergenCategory.GRASS),
        (Allergen.SILVER_GRASS, AllergenCategory.GRASS),
        (Allergen.RAGWEED, AllergenCategory.WEED),
        (Allergen.MUGWORT, AllergenCategory.WEED),
        (Allergen.ALTERNARIA, AllergenCategory.MOLD),
        (Allergen.HOUSE_DUST_MITE, AllergenCategory.DUST),
        (Allergen.PM25, AllergenCategory.AIR_QUALITY),
    ],
)
def test_named_allergens_group_under_their_category(
    allergen: Allergen, expected: AllergenCategory
) -> None:
    assert allergen_category(allergen) is expected


@pytest.mark.parametrize(
    ("legacy", "expected"),
    [
        (Allergen.TREE_POLLEN, AllergenCategory.TREE),
        (Allergen.GRASS_POLLEN, AllergenCategory.GRASS),
        (Allergen.WEED_POLLEN, AllergenCategory.WEED),
        (Allergen.MOLD, AllergenCategory.MOLD),
        (Allergen.DUST, AllergenCategory.DUST),
        (Allergen.OTHER, AllergenCategory.OTHER),
    ],
)
def test_legacy_coarse_values_still_resolve(legacy: Allergen, expected: AllergenCategory) -> None:
    """Rows written before B-005 must keep working — that is the migration path."""
    assert legacy in LEGACY_ALLERGENS
    assert resolve_allergen(legacy.value) is legacy
    assert allergen_category(legacy.value) is expected


def test_legacy_and_named_values_agree_on_category() -> None:
    """A user who recorded TREE_POLLEN scores the same as one who recorded BIRCH."""
    for named, legacy in [
        (Allergen.BIRCH, Allergen.TREE_POLLEN),
        (Allergen.TIMOTHY, Allergen.GRASS_POLLEN),
        (Allergen.RAGWEED, Allergen.WEED_POLLEN),
        (Allergen.ALTERNARIA, Allergen.MOLD),
        (Allergen.HOUSE_DUST_MITE, Allergen.DUST),
    ]:
        assert allergen_category(named) is allergen_category(legacy)


def test_legacy_set_is_exactly_the_coarse_members() -> None:
    named = {a for a in Allergen if a not in LEGACY_ALLERGENS}
    assert named | LEGACY_ALLERGENS == set(Allergen)
    assert not named & LEGACY_ALLERGENS
    # The named catalogue is what the picker offers, so it must actually exist.
    assert {Allergen.BIRCH, Allergen.TIMOTHY, Allergen.RAGWEED} <= named
    assert {Allergen.ALTERNARIA, Allergen.HOUSE_DUST_MITE} <= named


def test_unknown_stored_value_fails_loudly() -> None:
    # allergen is a plain VARCHAR, so a row from an unknown build can arrive.
    # Scored-as-unknown would silently drop the user's allergy match.
    with pytest.raises(ValueError, match="Unknown allergen"):
        resolve_allergen("DRAGON_SCALE")
    with pytest.raises(ValueError, match="Unknown allergen"):
        allergen_category("not-a-real-allergen")


def test_resolve_accepts_both_str_and_enum() -> None:
    assert resolve_allergen("BIRCH") is Allergen.BIRCH
    assert resolve_allergen(Allergen.BIRCH) is Allergen.BIRCH
