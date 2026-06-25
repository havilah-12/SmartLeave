import pytest
from database.connection import get_connection
import os

def test_get_connection():
    """Test that we can successfully connect to the database"""
    conn = get_connection()
    assert conn is not None
    conn.close()
