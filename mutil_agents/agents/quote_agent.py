"""Quote Agent - generates pricing quotes based on customer requests."""

import os
import dotenv
from smolagents import ToolCallingAgent, OpenAIServerModel
from mutil_agents.tools.quote_tools import get_quote_history_tool, generate_quote_tool

import json
from typing import List, Dict, Union, Optional
from smolagents import tool


@tool
def final_answer(
    quoted_items: Dict[str, Dict[str, Union[int, float, str]]],
    total_price: float,
    unavailable_items: List[str] = [],
    bulk_discount: str = "0%",
    recommendation: str = "",
) -> str:
    """
    Provides the final pricing quote with structured output.
    
    Args:
        quoted_items: Dict of item names to quote details (quantity, unit_price, discount, item_total)
        total_price: Final calculated total cost
        unavailable_items: Items that could not be quoted (default: empty list)
        bulk_discount: Highest discount percentage applied (default: "0%")
        recommendation: Summary and notes about the quote (default: empty)
    """
    return json.dumps({
        "quoted_items": quoted_items,
        "unavailable_items": unavailable_items,
        "total_price": round(total_price, 2),
        "bulk_discount": bulk_discount,
    })


class QuoteAgent(ToolCallingAgent):
    """Agent responsible for generating pricing quotes based on customer requests and historical data."""
    
    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="QuoteAgent",
            model=model,
            tools=[get_quote_history_tool, generate_quote_tool, final_answer],
            verbosity_level=verbosity_level,
            description="""You generate pricing quotes for customer orders. Inventory has already been validated.

REASONING PROCESS:

Step 1: EXTRACT REQUEST DETAILS
- Parse customer request for items and quantities
- Use EXACT item names from Inventory Status (the keys in 'items' dict)
- Example: Customer says "100 Sheets of 'A4 paper'" → Extract: item="A4 paper", qty=100
- Check Inventory Status['missing_items'] - these go directly to unavailable_items

Step 2: GET PRICING CONTEXT (OPTIONAL)
- Call get_quote_history_tool(search_terms="item_name") for historical pricing
- Use this context to understand typical pricing patterns

Step 3: GENERATE QUOTE
- Call generate_quote_tool(items="A4 paper", quantities="100")
- For multiple items: items="A4 paper,Cardstock", quantities="100,50"
- Use exact item names from Inventory Status['items']

Step 4: TRANSFORM OUTPUT
The generate_quote_tool returns:
{
  "quote_items": [{"item": "A4 paper", "quantity": 100, "unit_price": 2.5, "discount": "0%", "item_total": 250.0}],
  "total_amount": 250.0
}

Transform to final_answer format:
- Convert quote_items LIST to quoted_items DICT using "item" as key
- total_price = total_amount from tool
- bulk_discount = highest discount from all items
- unavailable_items = Inventory Status['missing_items']

Step 5: CALL FINAL_ANSWER
final_answer(
    quoted_items={"A4 paper": {"quantity": 100, "unit_price": 2.5, "discount": "0%", "item_total": 250.0}},
    total_price=250.0,
    unavailable_items=[],
    bulk_discount="0%",
)

DISCOUNT TIERS (applied per item by generate_quote_tool):
- 1-100 units: 0%
- 101-500 units: 5%
- 501-1000 units: 10%
- 1001+ units: 15%

CRITICAL RULES:
- Item names: Use exact strings from Inventory Status['items'] keys
- Always call final_answer to complete - even if all items unavailable
- Data transformation: quote_items (list) → quoted_items (dict with item name as key)
- If Inventory Status['missing_items'] has entries, copy them to unavailable_items

COMPLETE EXAMPLE:

Input:
Customer request: I would like to request 100 Sheets of 'A4 paper' (Date of request: 2025-03-01)
Inventory Status: {'items': {'A4 paper': 100}, 'missing_items': [], 'low_stock': [], 'reorder_required': False}

Execution:
1. Extract: item="A4 paper", quantity=100
2. get_quote_history_tool(search_terms="A4 paper") → review results
3. generate_quote_tool(items="A4 paper", quantities="100") → returns quote
4. Transform: quote_items list → quoted_items dict
5. final_answer(
     quoted_items={"A4 paper": {"quantity": 100, "unit_price": 2.5, "discount": "0%", "item_total": 250.0}},
     total_price=250.0,
     unavailable_items=[],
     bulk_discount="0%",
   )""",
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

    orchestrator = QuoteAgent(model=model, verbosity_level=1)

    result = orchestrator.run(
        """
        Customer request: I would like to request 100 Sheets of 'A4 paper' (Date of request: 2025-03-01)                                                                                                                        │
        Inventory Status: {'items': {'A4 paper': 100}, 'missing_items': [], 'low_stock': [], 'reorder_required': False}"""
    )

    print(result)
