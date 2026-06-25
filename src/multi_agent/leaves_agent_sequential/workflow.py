import re
from typing import Any
from datetime import datetime

from google.adk.workflow import Workflow, node
from google.genai import types

from sub_agents.employee_agent.agent import employee_agent
from sub_agents.holiday_agent.agent import holiday_agent
from sub_agents.leave_calculation_agent.agent import leave_calculation_agent
from sub_agents.leave_submission_agent.agent import leave_submission_agent
from shared.intent_slot_extractor import intent_slot_extractor
from shared.deterministic_nodes import (
    prepare_calculation_context, extract_calculation_payload, prepare_submission_context, submit_leave_node,
    missing_info_router, ask_missing_info
)

from shared.confirmation_classifier import pending_confirmation_router

@node(name="readiness_check_node")
def readiness_check_node(ctx: Any, node_input: Any) -> Any:
    """Check if the employee and holidays were found sequentially."""
    employee_ok = ctx.state.get("employee_lookup_status") == "found"
    holiday_ok = ctx.state.get("holiday_lookup_status") == "found"

    if not employee_ok:
        ctx.route = "employee_error"
        return types.Content(role="model", parts=[types.Part(text="Error: Could not find your employee details.")])
    elif not holiday_ok:
        ctx.route = "holiday_error"
        return types.Content(role="model", parts=[types.Part(text="Error: Could not retrieve holiday calendar.")])
    else:
        ctx.route = "ready"
        return "Dependencies verified"

@node(name="check_employee_intent")
def check_employee_intent(ctx: Any, node_input: Any) -> Any:
    if ctx.state.get("intent") == "employee_only":
        ctx.route = "end"
    else:
        ctx.route = "continue"
    return node_input

@node(name="check_holiday_intent")
def check_holiday_intent(ctx: Any, node_input: Any) -> Any:
    if ctx.state.get("intent") == "holiday_only":
        ctx.route = "end"
    else:
        ctx.route = "continue"
    return node_input

@node(name="check_submission_intent")
def check_submission_intent(ctx: Any, node_input: Any) -> Any:
    if ctx.state.get("intent") == "calculate_only":
        ctx.route = "end"
    else:
        ctx.route = "continue"
    return node_input

@node(name="start_employee_pipeline")
def start_employee_pipeline(ctx: Any, node_input: Any) -> Any:
    """Pass-through node that constructs strict delegator instructions for the sub-agents."""
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

@node(name="start_holiday_pipeline")
def start_holiday_pipeline(ctx: Any, node_input: Any) -> Any:
    """Pass-through node to strictly ask the holiday agent to fetch holidays."""
    instruction = "[SYSTEM DELEGATION] Do not converse. Execute your tool to fetch company holidays for the requested dates."
    return types.Content(role="user", parts=[types.Part(text=instruction)])

sequential_workflow = Workflow(
    name="leaves_agent_sequential",
    
    edges=[
        ("START", pending_confirmation_router, {
            "continue": intent_slot_extractor,
            "confirmed": submit_leave_node
        }),
        (intent_slot_extractor, missing_info_router),
        (missing_info_router, {
            "holiday_only": holiday_agent,
            "employee_only": employee_agent,
            "incomplete_request": ask_missing_info,
            "ready_for_pipeline": start_employee_pipeline
        }),
        (start_employee_pipeline, employee_agent),
        (employee_agent, check_employee_intent, {
            "continue": start_holiday_pipeline
        }),
        (start_holiday_pipeline, holiday_agent),
        (holiday_agent, check_holiday_intent, {
            "continue": readiness_check_node
        }),
        (readiness_check_node, {
            "ready": prepare_calculation_context
        }),
        (prepare_calculation_context, leave_calculation_agent),
        (leave_calculation_agent, extract_calculation_payload),
        (extract_calculation_payload, check_submission_intent, {
            "continue": prepare_submission_context
        }),
        (prepare_submission_context, leave_submission_agent)
    ]
)

root_agent = sequential_workflow
