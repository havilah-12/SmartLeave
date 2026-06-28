from typing import Any
from datetime import datetime

from google.adk.workflow import JoinNode, Workflow, node
from google.genai import types

from agents.employee_agent.agent import employee_agent as fetch_employee_node
from agents.holiday_agent.agent import holiday_agent as fetch_holiday_node

from nodes.intent_slot_extractor import parse_request_node
from nodes.validation_nodes import (
    validate_request_node, ask_missing_info, overlap_check_node, check_leave_preference_node,
    readiness_check_node, check_employee_intent, check_holiday_intent, greeting_node
)
from nodes.lookup_nodes import fetch_existing_leaves_node
from nodes.formatting_nodes import calculate_and_format_leave_node
from nodes.submission_nodes import submit_leave_node, revoke_leave_node

from nodes.confirmation_classifier import confirmation_node



@node(name="start_parallel")
def start_parallel(ctx: Any, node_input: Any) -> Any:
    """Fan-out node that constructs strict delegator instructions for the sub-agents."""
    emp_id = ctx.state.get("leave_request_employee_id")
    start = ctx.state.get("leave_request_start_date")
    end = ctx.state.get("leave_request_end_date")
    
    instruction = f"""[SYSTEM DELEGATION]
Please execute your tools to fetch data for the following request:
Today's Date: {datetime.now().strftime("%Y-%m-%d")}
Employee ID: {emp_id}
Start Date: {start}
End Date: {end}"""
    return types.Content(role="user", parts=[types.Part(text=instruction)])

join_node = JoinNode(name="sync_employee_and_holidays")

parallel_workflow = Workflow(
    name="leaves_agent_parallel",
    
    edges=[
        ("START", confirmation_node, {
            "continue": parse_request_node,
            "confirmed": submit_leave_node
        }),
        (parse_request_node, validate_request_node),
        (validate_request_node, {
            "holiday_only": fetch_holiday_node,
            "employee_only": fetch_employee_node,
            "revoke_leave": revoke_leave_node,
            "incomplete_request": ask_missing_info,
            "ready_for_pipeline": start_parallel,
            "greeting": greeting_node
        }),
        (start_parallel, (fetch_employee_node, fetch_holiday_node)),
        (fetch_holiday_node, check_holiday_intent, {
            "continue": join_node
        }),
        (fetch_employee_node, check_employee_intent, {
            "continue": join_node
        }),
        (join_node, readiness_check_node, {
            "ready": fetch_existing_leaves_node
        }),
        (fetch_existing_leaves_node, overlap_check_node, {
            "continue": check_leave_preference_node
        }),
        (check_leave_preference_node, {
            "continue": calculate_and_format_leave_node,
            "ask_preference": ask_missing_info
        })
    ]
)

root_agent = parallel_workflow

