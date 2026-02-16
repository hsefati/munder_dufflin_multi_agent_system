"""Quote Agent - generates pricing quotes based on customer requests."""

import os
import dotenv
from pydantic import BaseModel, Field, field_validator
from smolagents import ToolCallingAgent, OpenAIServerModel, CodeAgent
from mutil_agents.tools.quote_tools import get_quote_history_tool, generate_quote_tool

from typing import List, Dict
from smolagents import tool


class ItemDetail(BaseModel):
    quantity: int = Field(..., description="Number of units")
    unit_price: float = Field(..., description="Price per single unit")
    discount: str = Field(default="0%", description="Discount percentage applied")
    item_total: float = Field(
        ..., description="Total cost for this item (qty * price - discount)"
    )


class QuoteDetails(BaseModel):
    quoted_items: Dict[str, ItemDetail] = {}
    unavailable_items: List[str] = []
    total_price: float = 0.0
    bulk_discount: str = "0%"

    @field_validator("total_price")
    @classmethod
    def validate_total(cls, v, info):
        # Optional: Add logic to verify if v matches sum of quoted_items
        return round(v, 2)


@tool
def final_answer(
    quoted_items: Dict[str, Dict],
    total_price: float,
    unavailable_items: List[str] = [],
    bulk_discount: str = "0%",
) -> dict:
    """
    Provides the final pricing quote with structured output.

    Args:
        quoted_items: Map of item names to details like {'quantity': 10, 'unit_price': 5.0, 'discount': '0%', 'item_total': 50.0}
        total_price: Final calculated total cost (sum of item totals)
        unavailable_items: List of items that were requested but are out of stock.
        bulk_discount: The highest discount tier reached (e.g., '10%')
    """
    # 1. Handle the "Empty Inventory" edge case gracefully
    if not quoted_items:
        return {
            "quoted_items": {},
            "unavailable_items": unavailable_items,
            "total_price": 0.0,
            "bulk_discount": "0%",
            "status": "partial_or_empty_quote",
        }

    # 2. Validation using the Pydantic model defined above
    try:
        quote_data = QuoteDetails(
            quoted_items=quoted_items,
            unavailable_items=unavailable_items,
            total_price=total_price,
            bulk_discount=bulk_discount,
        )
        return quote_data.model_dump()
    except Exception as e:
        # If the LLM messed up the structure, return what we have with an error flag
        return {
            "error": f"Data validation failed: {str(e)}",
            "raw_data": {"quoted_items": quoted_items, "total_price": total_price},
        }


class QuoteAgent(CodeAgent):
    """Agent responsible for generating pricing quotes with strict multi-step validation."""

    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="QuoteAgent",
            model=model,
            tools=[get_quote_history_tool, generate_quote_tool, final_answer],
            verbosity_level=verbosity_level,
            description=""""
    You are a Strategic Sales Agent. Your goal is to generate quotes that maximize value and encourage bulk buying.
    
    STRATEGY:
    1. Before quoting, check history to understand past pricing for these items.
    2. Note the Discount Tiers: 5% at >100 units, 10% at >500 units, and 15% at >1000 units.
    3. If a user requests a quantity just below a tier (e.g., 95 units), generate the requested quote AND a second 'comparison' quote at the tier threshold (e.g., 101 units) to show them the savings.
    4. Always highlight the total discount applied in your final response to make the deal feel attractive.
    5. Use the 'final_answer' tool to return a structured quote.
    """,
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

    # inventory_manager_data = {
    #     "available_items": {"A4 paper": 172},
    #     "missing_items": [],
    #     "low_stock": [],
    #     "reorder_required": False,
    #     "delivery_timelines": {
    #         "A4 paper": {
    #             "supplier": "default supplier",
    #             "lead_time_days": 1,
    #             "estimated_delivery": "2025-03-02",
    #         }
    #     },
    # }

    # inventory_manager_data = {
    #     "available_items": {},
    #     "missing_items": [
    #         "A4 glossy paper",
    #         "heavy cardstock (white)",
    #         "colored paper (assorted colors)",
    #     ],
    #     "low_stock": [],
    #     "reorder_required": False,
    #     "delivery_timelines": {},
    # }
    # inventory_data = {
    #     "available_items": {
    #         "A4 glossy paper": 0,
    #         "heavy cardstock (white)": 0,
    #         "colored paper (assorted colors)": 0,
    #     },
    #     "missing_items": [
    #         "A4 glossy paper",
    #         "heavy cardstock (white)",
    #         "colored paper (assorted colors)",
    #     ],
    #     "low_stock": [],
    #     "reorder_required": True,
    #     "delivery_timelines": {
    #         "A4 glossy paper": "2025-04-05",
    #         "heavy cardstock (white)": "2025-04-02",
    #         "colored paper (assorted colors)": "2025-04-02",
    #     },
    # }

    inventory_data = {
        "requested_items": {"Paper plates": 100},
        "available_items": {"Paper plates": 748},
        "missing_items": [],
        "low_stock": [],
        "reorder_required": False,
        "delivery_timelines": {},
    }

    result = orchestrator.run(
        "Based on the given inventory information, generate a quote.",
        additional_args={"inventory_info": inventory_data},
    )
    print(result)
    # json_result = json.loads('{"quoted_items": {"A4 paper": {"quantity": 100, "unit_price": 0.05, "discount": "0%", "item_total": 5.0}}, "unavailable_items": [], "total_price": 5.0, "bulk_discount": "0%"}')
    # print()
