from worldcup_recap.schedule import phase_for_date, stage_for, _static_group_for, GROUPS


def test_phase_for_date():
    assert phase_for_date("2026-06-16") == "Group Stage"
    assert phase_for_date("2026-06-30") == "Round of 32"
    assert phase_for_date("2026-07-05") == "Round of 16"
    assert phase_for_date("2026-07-10") == "Quarterfinal"
    assert phase_for_date("2026-07-19") == "Final"
    assert phase_for_date("2026-08-01") is None


def test_static_group_for():
    assert _static_group_for("Argentina") == "Group J"
    assert _static_group_for("England") == "Group L"
    assert _static_group_for("Nowhere United") is None


def test_groups_are_complete():
    assert len(GROUPS) == 12
    all_teams = [t for teams in GROUPS.values() for t in teams]
    assert len(all_teams) == 48
    assert len(set(all_teams)) == 48  # no dupes


def test_stage_for_group_stage_uses_static_fallback():
    assert stage_for("Argentina", "Algeria", "2026-06-16") == "Group J"


def test_stage_for_group_stage_prefers_live_map():
    gm = {"Argentina": "Group Z"}
    assert stage_for("Argentina", "Algeria", "2026-06-16", gm) == "Group Z"


def test_stage_for_knockout():
    assert stage_for("Brazil", "Germany", "2026-07-10") == "Quarterfinal"
    assert stage_for("A", "B", "2026-07-19") == "Final"


def test_stage_for_unknown_group_stage_team():
    assert stage_for("Unknown A", "Unknown B", "2026-06-16") == "Group Stage"
