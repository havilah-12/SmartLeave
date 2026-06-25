import pytest
from sub_agents.leave_submission_agent.agent import leave_submission_agent

def test_leave_submission_agent_initialization():
    assert leave_submission_agent.name == "leave_submission_agent"
    assert leave_submission_agent.model == "gemini-2.5-flash"
