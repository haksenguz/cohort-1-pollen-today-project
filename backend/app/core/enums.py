from enum import StrEnum


class AllergenCategory(StrEnum):
    """What an allergen is, for scoring and display.

    Scoring matches on the category, not the exact species, so BIRCH and the
    legacy TREE_POLLEN behave identically without a data migration.
    """

    TREE = "TREE"
    GRASS = "GRASS"
    WEED = "WEED"
    MOLD = "MOLD"
    DUST = "DUST"
    AIR_QUALITY = "AIR_QUALITY"
    OTHER = "OTHER"


class Allergen(StrEnum):
    """Named allergens a person can actually recognise (B-005).

    "Tree pollen" is not something a hay-fever sufferer can say they are
    allergic to; birch, oak and Japanese cedar are.

    The legacy coarse values stay as members on purpose: `user_allergies.allergen`
    is a bare VARCHAR(30) with no CHECK constraint, so rows already hold them.
    They resolve to the same category as their named equivalents, which is the
    whole migration story — no DDL, no alembic revision.
    """

    # Tree
    BIRCH = "BIRCH"
    OAK = "OAK"
    ALDER = "ALDER"
    WILLOW = "WILLOW"
    POPLAR = "POPLAR"
    JAPANESE_CEDAR = "JAPANESE_CEDAR"
    PEACH = "PEACH"
    OLIVE = "OLIVE"
    # Grass
    TIMOTHY = "TIMOTHY"
    COCKSFOOT = "COCKSFOOT"
    ZOYSIA = "ZOYSIA"
    BERMUDA_GRASS = "BERMUDA_GRASS"
    SILVER_GRASS = "SILVER_GRASS"
    WEEPING_GRASS = "WEEPING_GRASS"
    # Weed
    RAGWEED = "RAGWEED"
    MUGWORT = "MUGWORT"
    COCKLEBUR = "COCKLEBUR"
    BEGGAR_TICKS = "BEGGAR_TICKS"
    LAMB_QUARTERS = "LAMB_QUARTERS"
    DOCK = "DOCK"
    # Fungal spore
    ALTERNARIA = "ALTERNARIA"
    CLADOSPORIUM = "CLADOSPORIUM"
    # Indoor
    HOUSE_DUST_MITE = "HOUSE_DUST_MITE"
    COCKROACH = "COCKROACH"
    # Particulates
    PM25 = "PM25"
    PM10 = "PM10"
    # Legacy coarse buckets — still accepted, never offered in the picker.
    TREE_POLLEN = "TREE_POLLEN"
    GRASS_POLLEN = "GRASS_POLLEN"
    WEED_POLLEN = "WEED_POLLEN"
    DUST = "DUST"
    MOLD = "MOLD"
    OTHER = "OTHER"


_TREE = (
    Allergen.BIRCH,
    Allergen.OAK,
    Allergen.ALDER,
    Allergen.WILLOW,
    Allergen.POPLAR,
    Allergen.JAPANESE_CEDAR,
    Allergen.PEACH,
    Allergen.OLIVE,
)
_GRASS = (
    Allergen.TIMOTHY,
    Allergen.COCKSFOOT,
    Allergen.ZOYSIA,
    Allergen.BERMUDA_GRASS,
    Allergen.SILVER_GRASS,
    Allergen.WEEPING_GRASS,
)
_WEED = (
    Allergen.RAGWEED,
    Allergen.MUGWORT,
    Allergen.COCKLEBUR,
    Allergen.BEGGAR_TICKS,
    Allergen.LAMB_QUARTERS,
    Allergen.DOCK,
)
_MOLD = (Allergen.ALTERNARIA, Allergen.CLADOSPORIUM)
_DUST = (Allergen.HOUSE_DUST_MITE, Allergen.COCKROACH)
_AIR = (Allergen.PM25, Allergen.PM10)

# Every member must appear here; `test_allergens.py` fails if one is missing.
ALLERGEN_CATEGORY: dict[Allergen, AllergenCategory] = {
    **{a: AllergenCategory.TREE for a in _TREE},
    **{a: AllergenCategory.GRASS for a in _GRASS},
    **{a: AllergenCategory.WEED for a in _WEED},
    **{a: AllergenCategory.MOLD for a in _MOLD},
    **{a: AllergenCategory.DUST for a in _DUST},
    **{a: AllergenCategory.AIR_QUALITY for a in _AIR},
    # Legacy buckets map onto the category of the species that replaced them.
    Allergen.TREE_POLLEN: AllergenCategory.TREE,
    Allergen.GRASS_POLLEN: AllergenCategory.GRASS,
    Allergen.WEED_POLLEN: AllergenCategory.WEED,
    Allergen.MOLD: AllergenCategory.MOLD,
    Allergen.DUST: AllergenCategory.DUST,
    Allergen.OTHER: AllergenCategory.OTHER,
}

# The pre-B-005 coarse values. Rows written before the switch hold these, so
# they must stay valid — they are just no longer offered in the picker.
LEGACY_ALLERGENS: frozenset[Allergen] = frozenset(
    {
        Allergen.TREE_POLLEN,
        Allergen.GRASS_POLLEN,
        Allergen.WEED_POLLEN,
        Allergen.DUST,
        Allergen.MOLD,
        Allergen.OTHER,
    }
)


def resolve_allergen(value: str | Allergen) -> Allergen:
    """Parse a stored or submitted allergen.

    Raises rather than falling back to a default: `allergen` is a plain
    VARCHAR, so a row written by an unknown build can arrive here, and quietly
    scoring it as "unmatched" would drop a real allergy match.
    """
    if isinstance(value, Allergen):
        return value
    try:
        return Allergen(value)
    except ValueError:
        raise ValueError(f"Unknown allergen: {value!r}") from None


def allergen_category(value: str | Allergen) -> AllergenCategory:
    """The scoring bucket for an allergen, named or legacy."""
    return ALLERGEN_CATEGORY[resolve_allergen(value)]


class AllergySeverity(StrEnum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class PollenLevel(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EMERGENCY = "EMERGENCY"


class TriageLevel(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    EMERGENCY = "EMERGENCY"


class AlertType(StrEnum):
    POLLEN = "POLLEN"
    AIR_QUALITY = "AIR_QUALITY"
    WEATHER = "WEATHER"
    GENERAL = "GENERAL"


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
