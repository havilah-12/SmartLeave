import pytest
from google.adk.workflow import Workflow
from workflows.leaves_agent_parallel.workflow import parallel_workflow

def test_parallel_workflow_compiles():
    assert isinstance(parallel_workflow, Workflow)
    assert parallel_workflow.name == "leaves_agent_parallel"
    
    # Check that it has edges
    assert len(parallel_workflow.edges) > 0


