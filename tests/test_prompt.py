"""A prompt for any chat AI: the question's topic picks PoB's reports; the reports kept short and lean."""
from poe2lab.assistant import prompt


def test_the_question_s_topic_picks_the_reports():
    assert prompt.topics_of("Почему я умираю от хаоса и что поменять в шмоте?") == ["defence", "gear"]
    assert prompt.topics_of("Какие пассивки взять дальше?") == ["tree"]
    assert prompt.topics_of("Как поднять DPS по боссам?") == ["damage"]
    assert prompt.reports_for(["defence", "gear"], False) == ["build_report", "stat_values"]
    assert prompt.reports_for([], False) == ["build_report"]  # no topic: the build report answers most
    assert prompt.reports_for(["target"], False) == ["build_report"]  # no guide: no target report
    assert prompt.reports_for(["target", "tree"], True) == ["tree_options", "target_report"]


def test_reports_are_lean():
    data = {"percentChange": {"dps": 4.783234, "ehp": 0.0, "chaos_hit": 0.01}, "value": 12.3456, "small": 0.12345}
    assert prompt._lean(data) == {"percentChange": {"dps": 4.8}, "value": 12.3, "small": 0.12}
    stats = [{"mod": f"m{i}", "percentChange": {"dps": float(i)}} for i in range(20)]
    assert [r["mod"] for r in prompt._trim("stat_values", stats)][:2] == ["m19", "m18"]
    assert len(prompt._trim("stat_values", stats)) == 12
