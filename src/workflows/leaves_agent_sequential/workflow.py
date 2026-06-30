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
from nodes.validation_nodes import validation_node



sequential_workflow = Workflow(
    name="leaves_agent_sequential",
    edges=[
        ("START", intent_router_node),
        (intent_router_node, {
            "run_pipeline": fetch_employee_node,
            "continue_calculation": calculation_agent,
            "submit_leave": submission_agent,
            "hr_action": hr_node
        }),
        (fetch_employee_node, validation_node),
        (validation_node, {
            "continue": fetch_holiday_node
        }),
        (fetch_holiday_node, calculation_agent)
    ]
)

root_agent = sequential_workflow
