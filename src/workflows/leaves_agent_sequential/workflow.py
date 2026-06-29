from typing import Any
from datetime import datetime

from google.adk.workflow import Workflow, node
from google.genai import types

from agents.employee_agent.agent import employee_agent as fetch_employee_node
from agents.holiday_agent.agent import holiday_agent as fetch_holiday_node
from agents.calculation_agent.agent import calculation_agent
from agents.submission_agent.agent import submission_agent
from nodes.intent_router import intent_router_node
from nodes.hr_node import hr_node

@node(name="end_node")
def end_node(ctx: Any, node_input: Any) -> Any:
    return node_input

sequential_workflow = Workflow(
    name="leaves_agent_sequential",
    edges=[
        ("START", intent_router_node),
        (intent_router_node, {
            "run_pipeline": fetch_employee_node,
            "ready_for_calculation": calculation_agent,
            "submit_leave": submission_agent,
            "hr_action": hr_node,
            "end": end_node
        }),
        (fetch_employee_node, fetch_holiday_node),
        (fetch_holiday_node, intent_router_node)
    ]
)

root_agent = sequential_workflow
