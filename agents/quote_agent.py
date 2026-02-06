"""Quote Agent - generates pricing quotes based on customer requests."""

from smolagents import ToolCallingAgent, OpenAIServerModel
from tools.quote_tools import get_quote_history_tool, generate_quote_tool


class QuoteAgent(ToolCallingAgent):
    """Agent responsible for generating pricing quotes based on customer requests and historical data."""
    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="QuoteAgent",
            model=model,
            tools=[get_quote_history_tool, generate_quote_tool],
            verbosity_level=verbosity_level,
            description="""Agent responsible for generating pricing quotes for customer orders.
            You have access to historical quote data and pricing information.
            
            Your responsibilities:
            - Analyze customer requests to understand their paper supply needs
            - Look up historical quotes to find comparable pricing
            - Apply bulk discounts based on order quantity:
              * 1-100 units: Standard pricing
              * 101-500 units: 5% discount
              * 501-1000 units: 10% discount
              * 1000+ units: 15% discount
            - Consider item type, quality, and previous customer relationships
            - Provide detailed quote explanations
            - Return final quote with itemized breakdown and total cost
            
            Always provide accurate calculations and competitive pricing.
            
            CRITICAL - FINAL OUTPUT RULE: After calculating the quote, you MUST respond with ONLY a valid JSON object in this exact format (no additional text):
            {
              "total_price": 1234.56,
              "itemized_breakdown": [{"item": "Paper Type A", "qty": 100, "price": 500.00}, ...],
              "discount_applied": "10%"
            }
            
            Do NOT use final_answer tool. Simply output the JSON as your final response.""",
        )
