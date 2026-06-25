from pydantic import BaseModel, EmailStr

class Employee(BaseModel):
    id: int
    name: str
    email: EmailStr
    leave_balance: int
