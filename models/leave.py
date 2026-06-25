from pydantic import BaseModel
from typing import Literal

class LeaveApplication(BaseModel):
    id: int | None = None
    employee_id: int
    start_date: str
    end_date: str
    total_days: int
    status: Literal['PENDING', 'CONFIRMED', 'REJECTED'] = 'PENDING'
