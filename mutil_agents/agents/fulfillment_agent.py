"""Fulfillment Agent - executes orders and manages shipment logistics."""

import os
import dotenv
from pydantic import BaseModel
from smolagents import ToolCallingAgent, OpenAIServerModel
from mutil_agents.tools.fulfillment_tools import (
    create_order_fulfillment_tool,
    check_delivery_timeline_tool,
)


class FulfillmentReceipt(BaseModel):
    status: str
    transaction_id: str
    delivery_date: str


class FulfillmentAgent(ToolCallingAgent):
    """Agent responsible for executing orders and managing shipment logistics."""

    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="FulfillmentAgent",
            model=model,
            tools=[create_order_fulfillment_tool, check_delivery_timeline_tool],
            verbosity_level=verbosity_level,
            description="""You are a Fulfillment Specialist. Your goal is to process approved quotes into finalized orders.

### INPUT CONTEXT
You will receive the following data in your context:
- `quote_details`: A dictionary containing 'item_name', 'quantity', and 'price_per_unit'.
- `request_date`: The date the order was placed.
- 'delivery_date': The estimated delivery date provided by the inventory agent.

### OPERATIONAL WORKFLOW
1. **Record Transaction:** Call `create_order_fulfillment_tool` using:
   - `item_name`: From `quote_details`
   - `quantity`: From `quote_details`
   - `price_per_unit`: From `quote_details`
   - `transaction_date`: Use the provided `request_date`
2. **Determine Logistics:** Call `check_delivery_timeline_tool` to get the estimated arrival date.
3. **Handle Errors:** If the fulfillment tool returns an error (e.g., "Insufficient Stock"), set the status to "error" in your final output.

### FINAL OUTPUT RULE
After tools are called, you must stop and provide a raw JSON object. 
Do NOT use the final_answer tool. Do NOT provide conversational filler.

Required JSON Format:
{
  "status": "success" | "error",
  "transaction_id": "ID_FROM_TOOL_OR_NULL",
  "delivery_date": "YYYY-MM-DD",
  "message": "Brief reason if error, otherwise empty"
}""",
        )


if __name__ == "__main__":
    dotenv.load_dotenv()
    OPENAI_API_KEY = os.getenv("UDACITY_OPENAI_API_KEY")
    SMOLAGENT_VERBOSITY = int(os.getenv("SMOLAGENT_VERBOSITY", "0"))

    model = OpenAIServerModel(
        model_id="gpt-4o-mini",
        api_base="https://openai.vocareum.com/v1",
        api_key=OPENAI_API_KEY,
    )

    agent = FulfillmentAgent(model=model, verbosity_level=1)

    quote_data = {
            "quoted_items": {
                "A4 paper": {
                    "quantity": 100,
                    "unit_price": 0.05,
                    "discount": "0%",
                    "item_total": 5.0,
                }
            },
            "unavailable_items": ["A4 paper"],
            "total_price": 5.0,
            "bulk_discount": "0%",
        }

    fulfillment_response = agent.run(
        "Please execute the order fulfillment based on the approved quote and customer request.",
        additional_args={
            "quote_details": quote_data,
            "request_date": '22025-03-01',
            "delivery_date": '2025-03-15',
        },
    )

    print(fulfillment_response)
