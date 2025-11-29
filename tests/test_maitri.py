import pytest

from logic import maitri, strengths


def test_temporary_maitri_offsets():
    # Sun in Aries (0), Mars in Gemini (2) -> 3rd house -> Friend
    # Jupiter in Leo (4) -> 5th house -> Enemy
    signs = {"Sun": 0, "Mars": 2, "Jupiter": 4}
    temp = maitri.compute_temporary_maitri(signs)

    assert temp["Sun"]["Mars"] == maitri.RELATION_FRIEND
    assert temp["Sun"]["Jupiter"] == maitri.RELATION_ENEMY


def test_compound_maitri_basic_cases():
    # Sun in Aries (0)
    # Jupiter (Natural Friend) in Leo (4) -> Temp Enemy
    # Friend + Enemy -> Neutral (Sama)
    signs = {"Sun": 0, "Jupiter": 4}
    comp = maitri.compute_compound_maitri(signs)
    assert comp["Sun"]["Jupiter"] == maitri.COMPOUND_SAMA

    # Mars (Natural Friend) in Gemini (2) -> Temp Friend
    # Friend + Friend -> Adhimitra
    signs["Mars"] = 2
    comp = maitri.compute_compound_maitri(signs)
    assert comp["Sun"]["Mars"] == maitri.COMPOUND_ADHIMITRA


def test_vimsopaka_score_own_and_friend():
    # Sun in Leo (Own) -> 20
    # Moon in Leo (Friend Sun) – for scoring, relationship is via sign lord.
    signs = {"Sun": 4, "Moon": 4}
    scores = strengths.calculate_vimsopaka_score(signs)

    assert scores["Sun"] == strengths.SCORE_OWN_EXALTED
    assert scores["Moon"] in {
        strengths.SCORE_ADHIMITRA,
        strengths.SCORE_MITRA,
        strengths.SCORE_SAMA,
        strengths.SCORE_SATRU,
        strengths.SCORE_ADHISATRU,
    }


def test_weighted_vimsopaka_shadvarga_simple():
    # Simple scenario: only D1 is provided; all groups should collapse to D1 score.
    planet = "Sun"
    sign_d1 = 4  # Leo (own sign)
    varga_positions = {1: sign_d1}
    compound = maitri.compute_compound_maitri({"Sun": sign_d1})

    weighted = strengths.calculate_weighted_vimsopaka_for_planet(
        planet,
        varga_positions=varga_positions,
        compound_maitri_d1=compound,
    )

    # Since only D1 is available and Sun is in own sign, all group scores should be 20.
    assert weighted["Shadvarga"] == strengths.SCORE_OWN_EXALTED
    assert weighted["Saptavarga"] == strengths.SCORE_OWN_EXALTED
    assert weighted["Dasavarga"] == strengths.SCORE_OWN_EXALTED
    assert weighted["Shodasavarga"] == strengths.SCORE_OWN_EXALTED
