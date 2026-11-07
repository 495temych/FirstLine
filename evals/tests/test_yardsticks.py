"""The two free yardsticks, on small hand-made sets."""

from evals import runner, yardsticks

FIX = {
    "family": "VPN",
    "paths": ["AUTO_FIX"],
    "tools": ["reset_vpn_profile"],
    "queues": [],
}
ROUTE = {"family": "DNS", "paths": ["ESCALATE"], "tools": [], "queues": ["NET-DNS"]}


def pair(text, answer):
    return ({"text": text}, answer)


TRAINING = [pair("vpn certificate failed tunnel", FIX)] * 3 + [
    pair("dns lookup nxdomain resolver", ROUTE)
] * 2


def test_a_target_is_the_first_path_with_its_tool_or_queue():
    assert yardsticks.target(FIX) == "AUTO_FIX|reset_vpn_profile|"
    assert yardsticks.target(ROUTE) == "ESCALATE||NET-DNS"
    both = {"paths": ["SELF_SERVE", "ESCALATE"], "tools": [], "queues": ["X"]}
    assert yardsticks.target(both) == "SELF_SERVE||"


def test_the_most_common_answer_is_a_constant():
    test = [pair("nothing like it", ROUTE)]
    result = yardsticks.score(test, TRAINING)["most_common"]
    assert result["path_accuracy"] == 0
    assert result["kappa"] == 0


def test_the_classifier_learns_from_the_text():
    test = [pair("dns resolver nxdomain lookup", ROUTE)]
    result = yardsticks.score(test, TRAINING)["classifier"]
    assert result["action_accuracy"] == 1
    assert result["team_accuracy"] == 1


def test_yardsticks_train_only_on_the_knowledge_base_split():
    assert yardsticks.TRAINING_SPLIT == "kb"
    assert len(runner.load_imported(yardsticks.TRAINING_SPLIT)) == 384
