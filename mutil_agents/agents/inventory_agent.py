"""Inventory Management - Two-Agent System"""

import os
import dotenv
from smolagents import ToolCallingAgent, OpenAIServerModel, tool
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
    missing_items: List[str] = [],
) -> str:
    """
    Provides the final inventory report.
    
    Args:
        items: Map of found items to quantities.
        missing_items: List of items requested but not found in the database.
    """
    if missing_items is None:
        missing_items = []
        
    return json.dumps(
        {
            "available_items": items,
            "missing_items": missing_items,
        }
    )

class InventoryCheckerAgent(ToolCallingAgent):
    """Agent responsible ONLY for checking current inventory levels."""
    
    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="InventoryCheckerAgent",
            model=model,
            tools=[check_inventory_tool, final_answer],  # Only inventory checking and final answer
            verbosity_level=verbosity_level,
            description="""Specialized agent for checking current stock levels.
            You have access to real-time inventory data through check_inventory_tool.
            
            Your sole responsibility:
            - Check current stock levels for requested paper supplies
            - Return accurate quantity information for items in the database
            - Identify items that are not found in the inventory system
            
            You do NOT handle reorder decisions or delivery timelines.
            Simply report what's currently in stock.""",
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
    
    orchestrator = InventoryCheckerAgent(model=model, verbosity_level=1)
    
    result = orchestrator.run(
        "I would like to request 100 Sheets of 'A4 paper'"
    )
    
    print(result)
