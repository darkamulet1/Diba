"""
Logic for Planetary Relationships (Maitri).
Includes:
1. Naisargika Maitri (Natural Relationships)
2. Tatkalika Maitri (Temporary Relationships based on chart position)
3. Panchadha Maitri (Compound Relationships)
"""

from typing import Dict

# Constants
PLANETS = [
    "Sun",
    "Moon",
    "Mars",
    "Mercury",
    "Jupiter",
    "Venus",
    "Saturn",
    "Rahu",
    "Ketu",
]

# Relationship Types
RELATION_FRIEND = "friend"
RELATION_NEUTRAL = "neutral"
RELATION_ENEMY = "enemy"

# Compound Relationship Types
COMPOUND_ADHIMITRA = "adhimitra"  # Intimate Friend
COMPOUND_MITRA = "mitra"  # Friend
COMPOUND_SAMA = "sama"  # Neutral
COMPOUND_SATRU = "satru"  # Enemy
COMPOUND_ADHISATRU = "adhisatru"  # Bitter Enemy

# Default Natural Relationships (Parashara)
# Format: Planet -> { 'friends': [], 'enemies': [], 'neutrals': [] (implicit) }
DEFAULT_NATURAL_RELATIONSHIPS = {
    "Sun": {"friends": ["Moon", "Mars", "Jupiter"], "enemies": ["Venus", "Saturn"]},
    "Moon": {
        "friends": ["Sun", "Mercury"],
        "enemies": [],
    },  # Moon has no enemies, rest are neutral
    "Mars": {"friends": ["Sun", "Moon", "Jupiter"], "enemies": ["Mercury"]},
    "Mercury": {"friends": ["Sun", "Venus"], "enemies": ["Moon"]},
    "Jupiter": {"friends": ["Sun", "Moon", "Mars"], "enemies": ["Mercury", "Venus"]},
    "Venus": {"friends": ["Mercury", "Saturn"], "enemies": ["Sun", "Moon"]},
    "Saturn": {
        "friends": ["Mercury", "Venus"],
        "enemies": ["Sun", "Moon", "Mars"],
    },
    # Standard view for nodes; can be tuned if needed
    "Rahu": {"friends": ["Venus", "Saturn"], "enemies": ["Sun", "Moon", "Mars"]},
    "Ketu": {"friends": ["Venus", "Saturn"], "enemies": ["Sun", "Moon", "Mars"]},
}


def get_natural_relationship(p1: str, p2: str) -> str:
    """Returns the natural relationship of p1 towards p2."""
    if p1 == p2:
        # Self – treat as neutral for Maitri scoring (Swakshetra handled elsewhere)
        return RELATION_NEUTRAL

    rels = DEFAULT_NATURAL_RELATIONSHIPS.get(p1, {})
    if p2 in rels.get("friends", []):
        return RELATION_FRIEND
    if p2 in rels.get("enemies", []):
        return RELATION_ENEMY
    return RELATION_NEUTRAL


def compute_temporary_maitri(planet_signs: Dict[str, int]) -> Dict[str, Dict[str, str]]:
    """
    Calculates Tatkalika Maitri (Temporary Relationship) based on positions.

    Rule: Planets in 2, 3, 4, 10, 11, 12 from a planet are temporary friends.
          Planets in 1, 5, 6, 7, 8, 9 are temporary enemies.

    Args:
        planet_signs: dict[planet_name] = sign_index (0..11)

    Returns:
        dict[planet][other] = RELATION_FRIEND or RELATION_ENEMY
    """
    temp_maitri: Dict[str, Dict[str, str]] = {p: {} for p in planet_signs}

    for p1, sign1 in planet_signs.items():
        for p2, sign2 in planet_signs.items():
            if p1 == p2:
                continue

            # Count from p1 to p2 in signs, 1..12
            count = (sign2 - sign1) % 12 + 1

            if count in (2, 3, 4, 10, 11, 12):
                temp_maitri[p1][p2] = RELATION_FRIEND
            else:
                temp_maitri[p1][p2] = RELATION_ENEMY

    return temp_maitri


def _combine_relationships(natural: str, temporary: str) -> str:
    """Combines natural and temporary relationships into Compound (Panchadha)."""
    if natural == RELATION_FRIEND and temporary == RELATION_FRIEND:
        return COMPOUND_ADHIMITRA
    if natural == RELATION_ENEMY and temporary == RELATION_ENEMY:
        return COMPOUND_ADHISATRU

    # Correct logic based on Friend/Enemy/Neutral + Friend/Enemy
    # Temp is only Friend or Enemy.
    if natural == RELATION_FRIEND:
        return COMPOUND_ADHIMITRA if temporary == RELATION_FRIEND else COMPOUND_SAMA

    if natural == RELATION_NEUTRAL:
        return COMPOUND_MITRA if temporary == RELATION_FRIEND else COMPOUND_SATRU

    if natural == RELATION_ENEMY:
        return COMPOUND_SAMA if temporary == RELATION_FRIEND else COMPOUND_ADHISATRU

    return COMPOUND_SAMA


def compute_compound_maitri(planet_signs: Dict[str, int]) -> Dict[str, Dict[str, str]]:
    """
    Computes Panchadha Maitri (Compound Relationships).

    Returns:
        dict where result[p1][p2] is the relationship of p1 towards p2.
    """
    temp_maitri = compute_temporary_maitri(planet_signs)
    compound_maitri: Dict[str, Dict[str, str]] = {p: {} for p in planet_signs}

    for p1 in planet_signs:
        for p2 in planet_signs:
            if p1 == p2:
                continue

            nat = get_natural_relationship(p1, p2)
            temp = temp_maitri[p1].get(p2, RELATION_ENEMY)

            compound_maitri[p1][p2] = _combine_relationships(nat, temp)

    return compound_maitri

