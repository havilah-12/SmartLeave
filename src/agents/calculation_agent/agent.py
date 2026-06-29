from google.adk.agents import Agent
from .prompt import CALCULATION_AGENT_PROMPT
from .tools import calculate_leave

calculation_agent = Agent(
    name="calculation_agent",
    instruction=CALCULATION_AGENT_PROMPT,
    model="gemini-2.5-flash",
    tools=[calculate_leave]
)
