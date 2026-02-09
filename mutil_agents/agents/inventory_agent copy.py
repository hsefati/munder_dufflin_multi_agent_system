"""Inventory Agent - manages inventory and stock levels."""

from smolagents import ToolCallingAgent, OpenAIServerModel
from smolagents import tool
from mutil_agents.tools.inventory_tools import (
    check_inventory_tool,
    check_reorder_status_tool,
    check_delivery_timeline_tool,
)
import json
from typing import Dict, List


@tool
def final_answer(
    items: Dict[str, int] = {},
    low_stock: List[str] = [],
    missing_items: List[str] = [],  # New field!
    reorder_required: bool = False,
    recommendation: str = "No information provided.",
) -> str:
    """
    Provides the final inventory report.

    Args:
        items: Map of found items to quantities.
        missing_items: List of items requested but not found in the database.
        low_stock: List of names of items below threshold. Use [] if none.
        reorder_required: Set to True if any stock is low or missing.
        recommendation: Summary of actions or status.
        ...
    """
    return json.dumps(
        {
            "items": items,
            "missing_items": missing_items,
            "low_stock": low_stock,
            "reorder_required": reorder_required,
            "recommendation": recommendation,
        }
    )


class InventoryAgent(ToolCallingAgent):
    """Agent responsible for managing inventory and stock levels."""

    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="InventoryAgent",
            model=model,
            tools=[
                check_inventory_tool,
                check_reorder_status_tool,
                check_delivery_timeline_tool,
                final_answer,
            ],
            verbosity_level=verbosity_level,
            description="""Agent responsible for managing inventory and stock levels.
            You have access to real-time inventory data and can:
            1. Check current stock levels for all paper supplies (check_inventory_tool)
            2. Monitor items and identify those running below minimum stock thresholds (check_reorder_status_tool)
            3. Estimate supplier delivery timelines for restocking orders (check_delivery_timeline_tool)
            
            Your responsibilities:
            - Provide accurate real-time inventory information
            - Proactively identify and alert about low stock situations
            - Assess reorder requirements based on current stock vs minimum thresholds
            - Estimate delivery times for restocking to help with capacity planning
            - Ensure inventory levels can meet customer demand
            
            When a customer requests items, first check availability. If stock is low, immediately 
            flag this for the orchestrator and provide delivery timeline estimates for restocking.""",
        )
