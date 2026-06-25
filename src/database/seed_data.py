import json
import os

# Simulating writing table definitions to a registry (like Firestore)
REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '..', 'table_registry.json')

def seed_registry():
    tables = {
        "employees": {
            "fields": ["id", "name", "email", "leave_balance"],
            "description": "Store employee details"
        },
        "holidays": {
            "fields": ["id", "date", "name"],
            "description": "Store public holidays"
        },
        "leave_applications": {
            "fields": ["id", "employee_id", "start_date", "end_date", "total_days", "status"],
            "description": "Store leave requests"
        }
    }
    
    with open(REGISTRY_PATH, 'w') as f:
        json.dump(tables, f, indent=4)
        
    print(f"Table registry seeded at {REGISTRY_PATH}")

if __name__ == '__main__':
    seed_registry()
