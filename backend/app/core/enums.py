from enum import StrEnum


class Allergen(StrEnum):
    TREE_POLLEN = "TREE_POLLEN"
    GRASS_POLLEN = "GRASS_POLLEN"
    WEED_POLLEN = "WEED_POLLEN"
    PM25 = "PM25"
    PM10 = "PM10"
    DUST = "DUST"
    MOLD = "MOLD"
    OTHER = "OTHER"


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
