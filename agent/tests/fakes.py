"""Stubs shared by the tests."""

from langchain_core.messages import AIMessage


def text(t):
    return {"type": "text", "text": t}


def tool(name, **inp):
    return {"type": "tool_use", "name": name, "input": inp}


class FakeLLM:
    def __init__(self, blocks):
        self.blocks = blocks
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
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
