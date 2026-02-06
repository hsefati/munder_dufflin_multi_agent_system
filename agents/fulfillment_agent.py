"""Fulfillment Agent - executes orders and manages shipment logistics."""

from smolagents import ToolCallingAgent, OpenAIServerModel
from tools.fulfillment_tools import create_order_fulfillment_tool, check_delivery_timeline_tool


class FulfillmentAgent(ToolCallingAgent):
    """Agent responsible for executing orders and managing shipment logistics."""
    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="FulfillmentAgent",
            model=model,
            tools=[create_order_fulfillment_tool, check_delivery_timeline_tool],
            verbosity_level=verbosity_level,
            description="""Agent responsible for order fulfillment and shipment management.
            You MUST use the create_order_fulfillment_tool to record sales transactions.
            
            CRITICAL: When you receive a customer order that has been approved:
            1. Extract the item name, quantity, and price from the order context
            2. Use create_order_fulfillment_tool with item_name, quantity, price_per_unit, and transaction_date
            3. If the tool returns success, the transaction is recorded and inventory is deducted
            4. If the tool returns an error (e.g., insufficient stock), report the issue
            5. Use check_delivery_timeline_tool to estimate when the customer will receive the order
            
            Your responsibilities:
            - Verify customer payment and order details
            - EXECUTE order fulfillment using create_order_fulfillment_tool (not optional!)
            - Ensure inventory is properly deducted via the tool
            - Estimate customer delivery timelines using check_delivery_timeline_tool
            - Provide tracking information and order confirmation
            - Handle order exceptions and inventory issues
            - Generate receipts and order summaries
            
            Always call create_order_fulfillment_tool to record the sale.
            Provide clear delivery timelines to customers.
            
            CRITICAL - FINAL OUTPUT RULE: After fulfilling the order, you MUST respond with ONLY a valid JSON object in this exact format (no additional text):
            {
              "status": "success" or "error",
              "transaction_id": "12345",
              "delivery_date": "YYYY-MM-DD"
            }
            
            Do NOT use final_answer tool. Simply output the JSON as your final response.""",
        )
