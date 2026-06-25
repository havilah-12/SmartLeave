from google.adk.agents import Agent
from sub_agents.employee_agent.tools import get_employee_details
from shared.prompts import EMPLOYEE_AGENT_PROMPT

employee_agent = Agent(
    name="employee_agent",
    instruction=EMPLOYEE_AGENT_PROMPT,
    model="gemini-2.5-flash",
    tools=[get_employee_details]
)
