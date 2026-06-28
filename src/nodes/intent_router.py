from typing import Any
from google.adk.workflow import node
from google.genai import Client

# We use a fast model for intent routing
ROUTER_MODEL = "gemini-2.5-flash"

ROUTER_PROMPT = """You are an Intent Classification Router for an HR Leave Management System.
Analyze the user's message and determine what they want to do.

You MUST reply with exactly ONE of these five labels, and absolutely nothing else:
1. `holiday_only` - If the user is ONLY asking about holidays (e.g., "What are the holidays this year?", "When is Diwali?")
2. `employee_only` - If the user is ONLY asking about their leave balance, profile, or history, but is NOT explicitly applying for new dates (e.g., "How many leaves do I have?", "What is my balance?", "Show my profile").
3. `calculate_only` - If the user ONLY wants to calculate leave days, working days, or check policy rules for specific dates.
4. `apply_leave` - If the user wants to apply for leave AND provides both dates and a reason.
5. `incomplete_request` - If the user wants to apply or calculate a leave, BUT they are missing either the dates OR the reason (e.g. "I want to apply for leave", "Simulate a leave calculation", "I want to take leave on Monday").

Message:
{message}
"""

@node(name="intent_router")
def intent_router(ctx: Any, node_input: Any) -> Any:
    """Classify the user intent into one of 3 paths: holiday_only, employee_only, apply_leave."""
    parts = getattr(ctx.user_content, "parts", None) or []
    user_text = " ".join(getattr(part, "text", "") for part in parts if getattr(part, "text", None)).strip()

    if not user_text:
        ctx.route = "apply_leave"
        return node_input

    client = Client()
    
    # We use generate_content to invoke the LLM for classification
    prompt = ROUTER_PROMPT.format(message=user_text)
    response = client.models.generate_content(model=ROUTER_MODEL, contents=prompt)
    
    raw_label = response.text.strip().lower()
    
    if "incomplete_request" in raw_label or "missing_dates" in raw_label:
        intent = "incomplete_request"
    elif "holiday_only" in raw_label:
        intent = "holiday_only"
    elif "employee_only" in raw_label:
        intent = "employee_only"
    elif "calculate_only" in raw_label:
        intent = "calculate_only"
    else:
        intent = "apply_leave"

    # Save the cleaned intent into the centralized shared memory
    ctx.state["intent"] = intent
    ctx.state["missing_fields"] = []

    # Route based on intent
    if intent == "holiday_only":
        ctx.route = "holiday_only"
    elif intent == "employee_only":
        ctx.route = "employee_only"
    elif intent == "incomplete_request":
        ctx.route = "incomplete_request"
    else:
        ctx.route = "apply_leave"
        
    return node_input
