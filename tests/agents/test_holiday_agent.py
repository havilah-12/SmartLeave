import pytest
from agents.holiday_agent.agent import holiday_agent

def test_holiday_agent_initialization():
    assert holiday_agent.name == "holiday_agent"
    assert holiday_agent.model == "gemini-2.5-flash"
    assert len(holiday_agent.tools) > 0
