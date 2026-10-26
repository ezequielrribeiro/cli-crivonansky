import pytest

from commands.complements.harness.contract import (
    ContractError,
    extract_blocks,
    parse_block,
)


def test_extract_blocks_from_markdown():
    text = "antes\n```crivonansky\ntask: git:run\n```\ndepois"
    blocks = extract_blocks(text)
    assert len(blocks) == 1
    assert "task: git:run" in blocks[0]


def test_parse_valid_block():
    block = parse_block("harness: 1\ntask: git:run\nparams:\n  args: [status]\n")
    assert block.task == "git:run"
    assert block.params["args"] == ["status"]
    assert block.return_to == "auto"


def test_parse_rejects_unknown_field():
    with pytest.raises(ContractError):
        parse_block("harness: 1\ntask: git:run\ndrop: true\n")


def test_parse_rejects_missing_task():
    with pytest.raises(ContractError):
        parse_block("harness: 1\nparams: {}\n")


def test_parse_rejects_wrong_harness_version():
    with pytest.raises(ContractError):
        parse_block("harness: 2\ntask: git:run\n")


def test_parse_rejects_invalid_return():
    with pytest.raises(ContractError):
        parse_block("harness: 1\ntask: git:run\nreturn: llm\n")


def test_parse_rejects_invalid_yaml():
    with pytest.raises(ContractError):
        parse_block("harness: 1\ntask: [\n")
