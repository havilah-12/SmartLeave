from google.adk.agents import Agent
from sub_agents.leave_calculation_agent.tools import calculate_working_days, stage_policy_evaluation
from shared.prompts import LEAVE_CALCULATION_AGENT_PROMPT

leave_calculation_agent = Agent(
    name="leave_calculation_agent",
    instruction=LEAVE_CALCULATION_AGENT_PROMPT,
    model="gemini-2.5-flash",
    tools=[calculate_working_days, stage_policy_evaluation]
)
