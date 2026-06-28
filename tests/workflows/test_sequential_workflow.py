import pytest
from google.adk.workflow import Workflow
from workflows.leaves_agent_sequential.workflow import sequential_workflow

def test_sequential_workflow_compiles():
    assert isinstance(sequential_workflow, Workflow)
    assert sequential_workflow.name == "leaves_agent_sequential"
    
    # Check that it has edges
    assert len(sequential_workflow.edges) > 0


