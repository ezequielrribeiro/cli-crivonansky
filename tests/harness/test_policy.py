from commands.complements.harness.contract import CommandBlock
from commands.complements.harness.policy import check_policy
from commands.complements.harness.types import TaskSpec


def _spec(intent="read"):
    return TaskSpec(
        name="t",
        intent=intent,
        description="",
        required=[],
        optional=[],
        handler=lambda ctx, params: None,
    )


def _block(params=None, intent=None):
    return CommandBlock(raw="", id="c-1", task="t", intent=intent, params=params or {})


def test_read_is_allowed():
    decision, _ = check_policy(_block(), _spec("read"), {}, True, False, False)
    assert decision == "allow"


def test_write_requires_confirmation():
    decision, _ = check_policy(_block(), _spec("write"), {}, True, False, False)
    assert decision == "confirm"


def test_write_denied_when_not_interactive():
    decision, _ = check_policy(_block(), _spec("write"), {}, False, False, False)
    assert decision == "deny"


def test_yes_allowed_overrides_confirmation():
    decision, _ = check_policy(_block(), _spec("write"), {}, False, True, True)
    assert decision == "allow"


def test_yes_not_allowed_for_llm_blocks():
    decision, _ = check_policy(_block(), _spec("write"), {}, False, False, True)
    assert decision == "deny"


def test_deny_pattern_blocks_command():
    config = {"policy": {"deny_patterns": [r"rm\s+-rf"]}}
    decision, _ = check_policy(_block({"command": "rm -rf /"}), _spec("write"), config, True, True, True)
    assert decision == "deny"


def test_block_cannot_downgrade_intent():
    decision, _ = check_policy(_block(intent="read"), _spec("write"), {}, True, False, False)
    assert decision == "confirm"


def test_docker_exec_read_only_intent():
    from commands.complements.harness.tasks.docker import intent_for

    assert intent_for({"command": "php -v"}) == "read"
    assert intent_for({"command": "ls /var/www/html"}) == "read"
    assert intent_for({"command": "php -l /var/www/html/index.php"}) == "read"
    assert intent_for({"command": "mysql --version"}) == "read"
    assert intent_for({"command": "rm -rf /tmp/x"}) == "write"
