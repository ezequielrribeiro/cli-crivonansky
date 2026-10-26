from commands.complements.harness.formatter import (
    collapse_repeats,
    format_result,
    mask_secrets,
    truncate,
)


def test_collapse_repeats():
    text = "erro\n" * 5
    assert "repetida" in collapse_repeats(text)


def test_truncate_short_text_is_untouched():
    text, truncated = truncate("abc", 100)
    assert text == "abc"
    assert truncated is False


def test_truncate_long_text_marks_truncated():
    text, truncated = truncate("x" * 5000, 1000)
    assert truncated is True
    assert len(text) <= 1200


def test_mask_secrets(monkeypatch):
    monkeypatch.setenv("HARNESS_DB_PASSWORD", "segredo123")
    config = {"legacy": {"db_password_env": "HARNESS_DB_PASSWORD"}}
    assert mask_secrets("senha=segredo123", config) == "senha=***"


def test_format_result_has_contract_fields():
    text, truncated = format_result(
        "c-1", "git:run", "success", 0, 10, "ok", "linha", [], 1000
    )
    assert text.startswith("```crivonansky-result")
    assert "status: success" in text
    assert "truncated: false" in text
    assert truncated is False
