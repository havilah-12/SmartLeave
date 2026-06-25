import pytest
from sub_agents.employee_agent.agent import employee_agent

def test_employee_agent_initialization():
    assert employee_agent.name == "employee_agent"
    assert employee_agent.model == "gemini-2.5-flash"
    assert len(employee_agent.tools) > 0
