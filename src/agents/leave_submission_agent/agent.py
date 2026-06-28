from google.adk.agents import Agent
from .prompt import LEAVE_SUBMISSION_AGENT_PROMPT

leave_submission_agent = Agent(
    name="leave_submission_agent",
    instruction=LEAVE_SUBMISSION_AGENT_PROMPT,
    model="gemini-2.5-flash"
)
