"""The agent's decision: one structured record, with its reasoning first.

The rationale comes first so the model reasons before it decides. The model only
records a decision here. Nothing runs until a person confirms it.
"""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from pydantic.config import JsonDict

from agent.tool_schemas import ESCALATION_TOOL, FIX_TOOLS, QUEUES

DECISION_TOOL_NAME = "record_decision"
DEFAULT_QUEUE = "DESK-SUPPORT"
DEFAULT_PRIORITY = "P3-Normal"
UNREADABLE = "The model's decision couldn't be read, so a person needs to look at it."
FIX_NAMES = [tool["name"] for tool in FIX_TOOLS]

Path = Literal["SELF_SERVE", "AUTO_FIX", "ESCALATE", "OUT_OF_SCOPE"]


def _one_of(values: list[str]) -> Callable[[JsonDict], None]:
    """Lists the allowed values in a field's schema."""

    def add(schema: JsonDict) -> None:
        schema["enum"] = list(values)

    return add


class Decision(BaseModel):
    """One triage decision. Fill the fields in order."""

    rationale: str = Field(
        description="The likely cause and the evidence for it, then why this path."
    )
    cause: str = Field(
        description=(
            "The cause's bold name from the playbook's Known causes, copied exactly. "
            "Use 'Unknown' if none fits, and 'None' for an out-of-scope request."
        )
    )
    path: Path
    steps: list[str] = Field(
        default=[], description="SELF_SERVE only: numbered steps for the user."
    )
    tool: str | None = Field(
        default=None,
        description="AUTO_FIX only: the remediation tool to propose.",
        json_schema_extra=_one_of(FIX_NAMES),
    )
    tool_input: dict[str, str] = Field(
        default={}, description="AUTO_FIX only: concrete values for the tool."
    )
    queue: str | None = Field(
        default=None,
        description="ESCALATE only: the queue that owns the next step.",
        json_schema_extra=_one_of(QUEUES),
    )
    summary: str = Field(
        default="", description="ESCALATE only: one sentence for the receiving team."
    )
    priority: Literal["P3-Normal", "P2-High", "P1-Critical"] = DEFAULT_PRIORITY


DECISION_TOOL = {
    "name": DECISION_TOOL_NAME,
    "description": "Record your triage decision.",
    "input_schema": Decision.model_json_schema(),
}


def _escalation(decision: Decision, queue: str) -> dict:
    return {
        "path": "ESCALATE",
        "tool_name": ESCALATION_TOOL,
        "tool_input": {
            "queue": queue,
            "summary": (decision.summary or decision.rationale)[:150],
            "priority": decision.priority,
        },
    }


def _action(decision: Decision) -> dict:
    """The path and tool. A decision that can't be carried out goes to a person."""
    if decision.path == "ESCALATE":
        queue = decision.queue or DEFAULT_QUEUE
        return _escalation(decision, queue if queue in QUEUES else DEFAULT_QUEUE)
    if decision.path == "AUTO_FIX":
        if decision.tool not in FIX_NAMES:
            return _escalation(decision, DEFAULT_QUEUE)
        return {
            "path": "AUTO_FIX",
            "tool_name": decision.tool,
            "tool_input": decision.tool_input,
        }
    return {"path": decision.path, "tool_name": None, "tool_input": None}


def _reasoning(decision: Decision) -> str:
    steps = [f"{n}. {step}" for n, step in enumerate(decision.steps, start=1)]
    return "\n\n".join(filter(None, [decision.rationale, "\n".join(steps)]))


def read_decision(arguments: dict | None, schema: type[Decision] = Decision) -> dict:
    """Turn the model's tool call into state. Anything unreadable goes to a person.
    The loop passes its own schema, whose extra fields come back as `extra`."""
    try:
        decision = schema.model_validate(arguments or {})
    except ValidationError:
        decision = schema(rationale=UNREADABLE, cause="Unknown", path="ESCALATE")
    extra = decision.model_dump(exclude=set(Decision.model_fields))
    return {
        **_action(decision),
        "reasoning": _reasoning(decision),
        "cause": decision.cause,
        **({"extra": extra} if extra else {}),
    }


def tool_guide() -> str:
    """The remediation tools, written out for the instructions."""
    lines = []
    for tool in FIX_TOOLS:
        parameters = ", ".join(tool["input_schema"]["properties"])
        lines.append(f"- `{tool['name']}({parameters})`: {tool['description']}")
    return "\n".join(lines)
