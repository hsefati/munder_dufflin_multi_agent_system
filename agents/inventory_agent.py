"""Inventory Agent - manages inventory and stock levels."""

from smolagents import ToolCallingAgent, OpenAIServerModel
from smolagents import tool
from tools.inventory_tools import (
    check_inventory_tool,
    check_reorder_status_tool,
    check_delivery_timeline_tool,
)


@tool
def final_answer(
    items=None, 
    low_stock=None, 
    reorder_required: bool = False, 
    recommendation: str = "No information provided.",
    restock_date=None
) -> str:
    """
    Provides the final inventory report. This tool MUST be used to finish the task.
    
    Args:
        items: Map of item names to quantities. Use {} if no items are found.
        low_stock: List of names of items below threshold. Use [] if none.
        reorder_required: Set to True if any stock is low or missing.
        recommendation: Summary of actions or status.
        restock_date: Estimated delivery (YYYY-MM-DD) or None.
    """
    import json
    if items is None:
        items = {}
    if low_stock is None:
        low_stock = []
    
    return json.dumps({
        "items": items,
        "low_stock": low_stock,
        "reorder_required": reorder_required,
        "restock_date": restock_date,
        "recommendation": recommendation
    })


class InventoryAgent(ToolCallingAgent):
    """Agent responsible for managing inventory and stock levels."""
    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="InventoryAgent",
            model=model,
            tools=[check_inventory_tool, check_reorder_status_tool, check_delivery_timeline_tool, final_answer],
            verbosity_level=verbosity_level,
            description="""Agent for real-time inventory and stock management.
            
            OPERATIONAL PIPELINE:
            1. Search for requested items using 'check_inventory_tool'.
            2. If items are low or missing, use 'check_reorder_status_tool' and 'check_delivery_timeline_tool'.
            3. Compile all data and call 'final_answer'.

            CRITICAL RULES:
            - You MUST call 'final_answer' to complete your task.
            - Even if an item is not found, you MUST provide all keys to 'final_answer'. 
            - If no items exist, set 'items' to {}, 'low_stock' to [], and 'reorder_required' to False.
            - Do not provide any conversational text before or after calling the tool.
            
            OUTPUT SCHEMA REQUIREMENTS:
            Your 'final_answer' call must include:
            - items (dict): {name: qty}
            - low_stock (list): [names]
            - reorder_required (bool)
            - restock_date (str/null)
            - recommendation (str)""",
        )
