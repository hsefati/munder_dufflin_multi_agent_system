import os
from typing import Dict, List
import dotenv
from pydantic import BaseModel
from smolagents import ToolCallingAgent, OpenAIServerModel, tool, CodeAgent
from mutil_agents.tools.inventory_tools import (
    check_reorder_status_tool,
    check_delivery_timeline_tool,
    check_inventory_tool
)
import json


class InventoryManagerStatus(BaseModel):
    available_items: Dict[str, int]
    missing_items: list
    low_stock: list
    reorder_required: bool
    delivery_timelines: Dict[str, str] = {}


@tool
def final_answer(
    available_items: Dict[str, int],
    low_stock: List[str],
    missing_items: List[str] = [],
    reorder_required: bool = False,
    delivery_timelines: Dict[str, Dict] = {},
) -> dict:
    """
    Provides the final structured inventory report. This MUST be your final action.

    Args:
        available_items: Map of item names to quantities currently in stock.
        low_stock: List of item names currently below the safety threshold.
        missing_items: List of requested items that were not found in inventory.
        reorder_required: Whether any items need to be reordered.
        delivery_timelines: Map of item names to their specific delivery/supplier info.

    Returns:
        The complete inventory analysis report.
    """

    return {
        "available_items": available_items,
        "missing_items": missing_items,
        "low_stock": low_stock,
        "reorder_required": reorder_required,
        "delivery_timelines": delivery_timelines,
    }


class InventoryManagerAgent(CodeAgent):
    """Agent responsible for reorder decisions and delivery logistics."""

    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="InventoryManagerAgent",
            model=model,
            tools=[
                check_reorder_status_tool,
                check_delivery_timeline_tool,
                check_inventory_tool,
                final_answer
            ],
            verbosity_level=verbosity_level,
            description="""
    You are an expert Inventory Manager. When a user asks about stock:
    1. First, check the current inventory levels.
    2. Second, check the reorder status to see if levels are below the minimum required.
    3. If a reorder is necessary (needs_reorder is True), use the delivery timeline tool 
       to find out when new stock would arrive if ordered today.
    4. Provide a consolidated summary: Current stock, whether a reorder is needed, 
       and the expected arrival date for replenishment.
    5. Always use the final_answer tool to return your response.
    """,
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

    agent = InventoryManagerAgent(model=model, verbosity_level=1)

    inventory_dict = {"available_items": {"A4 paper": 100}, "missing_items": []}
    inventory_dict = {
        "available_items": {},
        "missing_items": {
            "A4 glossy paper": 200,
            "heavy cardstock (white)": 100,
            "colored paper (assorted colors)": 100,
        },
    }
    result = agent.run(
        "Please process the inventory report for the provided customer request.",
        additional_args={
            "current_inventory": inventory_dict,
        },
    )

    print("Raw Result:")
    print(result)
    result = InventoryManagerStatus(**result)

    print(result.model_dump())
