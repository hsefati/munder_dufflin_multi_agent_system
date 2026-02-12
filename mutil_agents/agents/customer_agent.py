"""Customer Agent - plays the role of a customer reviewing and approving/declining quotes."""

import os
import dotenv
from pydantic import BaseModel
from smolagents import ToolCallingAgent, OpenAIServerModel, tool, CodeAgent


class CustomerDecision(BaseModel):
    decision: str  # "APPROVE" or "DECLINE"
    reason: str


@tool
def final_answer(
    decision: str,
    reason: str,
) -> dict:
    """
    Provides the final decision on the quote review.

    Args:
        decision: Must be either 'APPROVE' or 'DECLINE'
        reason: Brief explanation for your decision
    """
    decision = decision.upper().strip()

    # Validate and default to APPROVE if invalid
    if decision not in ["APPROVE", "DECLINE"]:
        decision = "APPROVE"
        reason = f"Invalid format, defaulting to APPROVE. {reason}"

    return {"decision": decision, "reason": reason}


class CustomerAgent(CodeAgent):
    """Agent playing the role of a customer reviewing and approving/declining quotes."""

    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="CustomerAgent",
            model=model,
            tools=[final_answer],  # Pass the custom final_answer tool
            verbosity_level=verbosity_level,
            description="""You are a customer reviewing a quote. 
            You have access to 'quote_summary' and 'original_request' in your local variables.
            
            Your default stance is to APPROVE unless:
            1. Critical requested items are missing.
            2. The total price is unreasonably high.
            3. Delivery timelines exceed requirements.
            
            Always use final_answer to return your decision.""",
        )


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    dotenv.load_dotenv()
    OPENAI_API_KEY = os.getenv("UDACITY_OPENAI_API_KEY")
    SMOLAGENT_VERBOSITY = int(os.getenv("SMOLAGENT_VERBOSITY", "0"))

    model = OpenAIServerModel(
        model_id="gpt-4o-mini",
        api_base="https://openai.vocareum.com/v1",
        api_key=OPENAI_API_KEY,
    )

    customer = CustomerAgent(model=model, verbosity_level=1)

    quote_data = {
        "quoted_items": {
            "A4 glossy paper": {
                "quantity": 200,
                "unit_price": 0.1,
                "discount": "0%",
                "item_total": 20.0,
            },
            "heavy cardstock (white)": {
                "quantity": 200,
                "unit_price": 0.15,
                "discount": "0%",
                "item_total": 30.0,
            },
            "colored paper (assorted colors)": {
                "quantity": 200,
                "unit_price": 0.12,
                "discount": "0%",
                "item_total": 24.0,
            },
        },
        "unavailable_items": [],
        "total_price": 74.0,
        "bulk_discount": "0%",
    }

    customer_request = """
I would like to request the following paper supplies for the ceremony:

- 200 sheets of A4 glossy paper
- 100 sheets of heavy cardstock (white)
- 100 sheets of colored paper (assorted colors)

I need these supplies delivered by April 15, 2025. Thank you. (Date of request: 2025-04-01)
"""

    result = customer.run(
        """
    Review the 'quote_summary' and 'original_request'. 
    
    1. Check if the 'quoted_items' match what the customer wanted.
    2. Evaluate if the 'bulk_discount' makes the deal attractive.
    3. IMPORTANT: Check 'unavailable_items'. If critical items are missing, 
       consider if the delivery delay is acceptable.
    
    Provide a final decision (Approve/Decline) and a brief justification 
    mentioning the total price and the impact of discounts.
    """,
        additional_args={
            "quote_summary": {
                "total": quote_data["total_price"],
                "items": quote_data["quoted_items"],
                "discount_applied": quote_data["bulk_discount"],
                "out_of_stock": quote_data["unavailable_items"],
            },
            "original_request": customer_request,
        },
    )

    print(result)
