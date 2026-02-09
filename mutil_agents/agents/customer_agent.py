"""Customer Agent - plays the role of a customer reviewing and approving/declining quotes."""

import os
import dotenv
from smolagents import ToolCallingAgent, OpenAIServerModel, tool

@tool
def final_answer(
    decision: str,
    reason: str,
) -> str:
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
    
    return f"DECISION: {decision}\nREASON: {reason}"


class CustomerAgent(ToolCallingAgent):
    """Agent playing the role of a customer reviewing and approving/declining quotes."""
    
    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="CustomerAgent",
            model=model,
            tools=[final_answer],  # Pass the custom final_answer tool
            verbosity_level=verbosity_level,
            description="""You are a customer reviewing a quote. Your default stance is to APPROVE unless there are critical issues.

You MUST use the final_answer tool to provide your decision:
final_answer(decision="APPROVE", reason="your explanation")
OR
final_answer(decision="DECLINE", reason="your explanation")

DECLINE ONLY IF:
- No items listed AND price is clearly wrong or unreasonable
- Critical requested items are completely missing
- Delivery timeline is unacceptable or unreasonably long

OTHERWISE APPROVE. Minor issues like missing discounts, empty item lists with reasonable pricing, or small concerns are NOT grounds for decline.""",
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
    
    orchestrator = CustomerAgent(model=model, verbosity_level=1)
    
    result = orchestrator.run(
        """
        Review this quote and decide:                                                                                                                                                                                           │
        Total Price: $5.0                                                                                                                                                                                                       │
        Items: {}                                                                                                                                                                                                               │
        Discount: 0%"""
    )
    
    print(result)