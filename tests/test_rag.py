from pentestagent.services.rag import format_snippet


def test_format_snippet_respects_character_budget():
    snippet = format_snippet("source", "abcdef", 3)

    assert snippet == "Source: source\nabc"

