import pytest
from agents.leave_calculation_agent.agent import leave_calculation_agent

def test_leave_calculation_agent_initialization():
    assert leave_calculation_agent.name == "leave_calculation_agent"
    assert leave_calculation_agent.model == "gemini-2.5-flash"
    assert len(leave_calculation_agent.tools) > 0
