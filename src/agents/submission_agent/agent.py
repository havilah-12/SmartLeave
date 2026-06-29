from google.adk.agents import Agent
from .prompt import SUBMISSION_AGENT_PROMPT
from .tools import submit_leave, revoke_leave

submission_agent = Agent(
    name="submission_agent",
    instruction=SUBMISSION_AGENT_PROMPT,
    model="gemini-2.5-flash",
    tools=[submit_leave, revoke_leave]
)
