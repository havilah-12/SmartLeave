from google.adk.agents import Agent
from agents.holiday_agent.tools import get_holidays
from .prompt import HOLIDAY_AGENT_PROMPT

holiday_agent = Agent(
    name="holiday_agent",
    instruction=HOLIDAY_AGENT_PROMPT,
    model="gemini-2.5-flash",
    tools=[get_holidays]
)
