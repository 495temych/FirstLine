"""Stubs shared by the tests."""

from langchain_core.messages import AIMessage

from agent.decision import DECISION_TOOL_NAME


def text(t):
    return {"type": "text", "text": t}


def decision(path, rationale="Because.", cause="Unknown", **fields):
    """The model's recorded decision, as blocks."""
    arguments = {"rationale": rationale, "cause": cause, "path": path, **fields}
    return [{"type": "tool_use", "name": DECISION_TOOL_NAME, "input": arguments}]


def fix(tool, rationale="Because.", **inp):
    return decision("AUTO_FIX", rationale, tool=tool, tool_input=inp)


def escalate(queue, rationale="Because.", summary="Needs review", priority="P2-High"):
    return decision(
        "ESCALATE", rationale, queue=queue, summary=summary, priority=priority
    )


def steps(*items, rationale="Because."):
    return decision("SELF_SERVE", rationale, steps=list(items))


def out_of_scope(rationale="Not an IT question."):
    return decision("OUT_OF_SCOPE", rationale)


class FakeLLM:
    def __init__(self, blocks):
        self.blocks = blocks
        self.bound_tools = None
        self.tool_choice = None

    def bind_tools(self, tools, tool_choice=None):
        self.bound_tools = tools
        self.tool_choice = tool_choice
        return self

    def invoke(self, messages):
        calls = [
            {"name": b["name"], "args": b["input"], "id": "x", "type": "tool_call"}
            for b in self.blocks
            if b["type"] == "tool_use"
        ]
        return AIMessage(content=self.blocks, tool_calls=calls)


UNIT = {
    "doc": "vpn",
    "section": None,
    "text": "VPN playbook",
    "score": 0.8,
    "highlights": [],
}


def call(name, **arguments):
    """One tool call the model makes, as a block."""
    return {"type": "tool_use", "name": name, "input": arguments}


class ScriptedLLM:
    """A model that plays one turn after another, repeating the last when it runs
    out. It records the tools bound and the messages of each turn."""

    def __init__(self, *turns, usage=None, broken=None):
        self.turns = list(turns)
        self.usage = usage
        self.broken = broken or []
        self.bound: list[list[str]] = []
        self.choices: list = []
        self.seen: list[list] = []
        self._tools: list[str] = []
        self._choice = None

    def bind_tools(self, tools, tool_choice=None):
        self._tools = [tool["name"] for tool in tools]
        self._choice = tool_choice
        return self

    def invoke(self, messages):
        number = len(self.seen)
        self.bound.append(self._tools)
        self.choices.append(self._choice)
        self.seen.append(list(messages))
        blocks = self.turns[min(number, len(self.turns) - 1)]
        calls = [
            {
                "name": b["name"],
                "args": b["input"],
                "id": f"call-{number}-{i}",
                "type": "tool_call",
            }
            for i, b in enumerate(blocks)
            if b["type"] == "tool_use"
        ]
        invalid = [
            {
                "name": name,
                "args": "{not json",
                "id": f"bad-{number}-{i}",
                "error": "bad",
                "type": "invalid_tool_call",
            }
            for i, name in enumerate(self.broken if number == 0 else [])
        ]
        texts = [b for b in blocks if b["type"] == "text"]
        return AIMessage(
            content=texts or "",
            tool_calls=calls,
            invalid_tool_calls=invalid,
            usage_metadata=self.usage,
        )
