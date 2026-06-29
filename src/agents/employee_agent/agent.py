from google.adk.agents import Agent
from agents.employee_agent.tools import get_employee_details, lookup_existing_leaves
from .prompt import EMPLOYEE_AGENT_PROMPT

employee_agent = Agent(
    name="employee_agent",
    instruction=EMPLOYEE_AGENT_PROMPT,
    model="gemini-2.5-flash",
    tools=[get_employee_details, lookup_existing_leaves]
)
