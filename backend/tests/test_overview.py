"""The "How it works" page's facts, checked against the code they describe."""

import inspect
import json

from fastapi.testclient import TestClient

from agent import config, graph, rules
from agent.tool_schemas import ESCALATION_TOOL, TOOL_POLICY, TOOLS
from backend import main, overview, stats

END = "__end__"


def test_every_node_of_the_graph_is_explained():
    assert set(overview.graph_nodes()) == set(overview.STATIONS)
    for station in overview.STATIONS.values():
        assert station["name"]
        assert station["does"]
        assert station["cannot"]
        assert station["code"]


def test_the_gates_are_exactly_the_nodes_that_wait_for_a_person():
    waits = {
        node
        for node in overview.graph_nodes()
        if "interrupt(" in inspect.getsource(getattr(graph, node))
    }
    gates = {node for node, s in overview.STATIONS.items() if s.get("gate")}
    assert gates == waits


def test_every_path_has_a_line():
    assert [line["path"] for line in overview.LINES] == stats.PATHS


def follows_the_graph(route: list[str]) -> bool:
    edges = overview.graph_edges()
    return all((a, b) in edges for a, b in zip(route, route[1:], strict=False))


def test_each_line_is_a_route_the_graph_really_takes():
    assert follows_the_graph(["__start__", *overview.TRUNK])
    for line in overview.LINES:
        main_route = [overview.TRUNK[-1], *line["stations"], END]
        assert follows_the_graph(main_route), line["path"]
        if line["stations"]:
            gate = line["stations"][0]
            otherwise = [gate, *line["otherwise"], END]
            assert follows_the_graph(otherwise), line["path"]


def test_every_rule_is_explained_and_names_code_that_exists():
    listed = overview.rules_list()
    assert [r["name"] for r in listed] == list(rules.RULES)
    for row in listed:
        assert row["does"]
        function, _, _ = row["code"].partition(" in ")
        assert getattr(rules, function) is rules.RULES[row["name"]]


def test_every_tool_is_explained_with_its_risk():
    rows = {row["name"]: row for row in overview.tools()}
    assert set(rows) == {tool["name"] for tool in TOOLS}
    for name, row in rows.items():
        assert row["does"]
        assert row["tier"] in overview.TIERS
        assert name == ESCALATION_TOOL or name in TOOL_POLICY


def test_the_page_reads_the_model_and_its_price_from_the_config(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-5-5")
    model = overview.model()
    assert model["name"] == "claude-sonnet-5-5"
    assert (model["input_usd_per_million"], model["output_usd_per_million"]) == (
        2.0,
        10.0,
    )


def test_examples_come_from_the_development_set_only():
    splits = json.loads((config.TICKETS_DIR / "splits.json").read_text())
    examples = overview._example_tickets()
    assert examples
    assert {e["id"] for e in examples.values()} <= set(splits["dev"])
    for path, example in examples.items():
        assert path in stats.PATHS
        assert example["title"]
        assert isinstance(example["retrieved"], list)


def test_a_saved_list_reads_back_as_a_list():
    assert overview._listed("['vpn', 'sec-02']") == ["vpn", "sec-02"]
    assert overview._listed("[]") == []
    assert overview._listed(["a"]) == ["a"]


def test_no_saved_run_means_no_result_and_no_examples(monkeypatch, tmp_path):
    monkeypatch.setattr(overview.runner, "RUNS_DIR", tmp_path)
    assert overview._result() is None
    assert overview._example_tickets() == {}


def test_the_overview_route_says_what_is_connected(monkeypatch):
    monkeypatch.delenv("QDRANT_URL", raising=False)
    body = TestClient(main.app).get("/api/overview").json()
    services = {s["name"]: s for s in body["services"]}
    assert services["Git"]["connected"] is True
    assert services["Qdrant"]["connected"] is False
    assert body["goal"]["break_even"] == 2 / 15
    assert body["result"]["n"] > 0
    assert set(body["stations"]) == set(overview.STATIONS)
    assert body["versions"]["version"]
