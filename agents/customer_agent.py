"""Customer Agent - plays the role of a customer reviewing and approving/declining quotes."""

from smolagents import ToolCallingAgent, OpenAIServerModel


class CustomerAgent(ToolCallingAgent):
    """Agent playing the role of a customer reviewing and approving/declining quotes."""
    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="CustomerAgent",
            model=model,
            tools=[],
            verbosity_level=verbosity_level,
            description="""Agent acting as the customer reviewing the presented quote.
            
            CRITICAL REQUIREMENT: You MUST respond with ONE of these exact formats:
            
            To APPROVE:
            DECISION: APPROVE
            REASON: [Brief explanation why you approve]
            
            To DECLINE:
            DECISION: DECLINE
            REASON: [Brief explanation why you decline]
            
            Your responsibilities:
            - Review the quote presented by the QuoteAgent
            - Evaluate the pricing, items, quantities, and delivery timeline
            - Decide whether to APPROVE or DECLINE the offer
            
            Decision criteria:
            - Consider if the price is reasonable
            - Check if delivery timeline meets the requirement
            - Verify all requested items are included
            
            MANDATORY: Your response MUST start with exactly "DECISION: APPROVE" or "DECISION: DECLINE" on the first line.""",
        )
