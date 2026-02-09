import os
import dotenv
from smolagents import ToolCallingAgent, OpenAIServerModel, tool
from mutil_agents.tools.inventory_tools import (
    check_reorder_status_tool,
    check_delivery_timeline_tool,
)
import json


@tool
def final_answer(
    available_items: str,
    low_stock: str = "[]",
    missing_items: str = "[]",
    reorder_required: str = "false",
    delivery_timelines: str = "{}",
) -> str:
    """
    Provides the final structured inventory report. This MUST be your final action.
    
    Args:
        available_items: JSON string of item names to quantities, e.g. '{"A4 paper": 100}'
        low_stock: JSON string list of item names below threshold, e.g. '["A4 paper"]' or '[]'
        missing_items: JSON string list of requested items not found, e.g. '["stapler"]' or '[]'
        reorder_required: String "true" if reordering needed, "false" otherwise
        delivery_timelines: JSON string of item names to delivery info, e.g. '{"A4 paper": {"supplier": "XYZ", "lead_time_days": 5, "estimated_delivery": "2025-03-06"}}'
    
    Returns:
        JSON string with complete inventory analysis including delivery data
    """
    try:
        available_items_dict = json.loads(available_items) if isinstance(available_items, str) else available_items
        low_stock_list = json.loads(low_stock) if isinstance(low_stock, str) else low_stock
        missing_list = json.loads(missing_items) if isinstance(missing_items, str) else missing_items
        reorder_bool = reorder_required.lower() == "true" if isinstance(reorder_required, str) else reorder_required
        delivery_dict = json.loads(delivery_timelines) if isinstance(delivery_timelines, str) else delivery_timelines
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON format: {str(e)}"})
    
    return json.dumps(
        {
            "available_items": available_items_dict,
            "missing_items": missing_list,
            "low_stock": low_stock_list,
            "reorder_required": reorder_bool,
            "delivery_timelines": delivery_dict,
        },
        indent=2
    )


class InventoryManagerAgent(ToolCallingAgent):
    """Agent responsible for reorder decisions and delivery logistics."""
    
    def __init__(self, model: OpenAIServerModel, verbosity_level: int = 0):
        super().__init__(
            name="InventoryManagerAgent",
            model=model,
            tools=[
                check_reorder_status_tool,
                check_delivery_timeline_tool,
                final_answer,
            ],
            verbosity_level=verbosity_level,
            description="""You are a specialized inventory management agent. Follow this process:
            
            Your input will be provided in two variables:
                1. 'customer_request': A string describing what the user wants.
                2. 'current_inventory': A dictionary containing 'available_items' and 'missing_items'.

            Follow this process:
            STEP 1: Analyze the current inventory data provided
            - Compare current stock levels against minimum thresholds
            - Identify items at or below reorder points


            STEP 2: For each low-stock or missing item:
            - Use check_reorder_status_tool to determine exact reorder requirements
            - Use check_delivery_timeline_tool to estimate supplier lead times
            - Store the delivery timeline information for each item


            STEP 3: Generate final report using final_answer tool with:
            - available_items: All inventory items with quantities
            - low_stock: Items below threshold (empty list if none)
            - missing_items: Requested items not in inventory
            - reorder_required: true if any item needs reorder, false otherwise
            - delivery_timelines: Dictionary mapping item names to their delivery information from check_delivery_timeline_tool (e.g., {"A4 paper": {"supplier": "Office Depot", "lead_time_days": 5, "estimated_delivery": "2025-03-06"}})


            IMPORTANT: 
            - Collect ALL delivery timeline data from check_delivery_timeline_tool calls
            - Structure delivery data as a dictionary with item names as keys
            - Always call final_answer as your last step with ALL collected information
            - Pass delivery_timelines as a JSON string to final_answer""",
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
    
    inventory_dict = {
        "available_items": {"A4 paper": 100},
        "missing_items": []
    }
    result = agent.run(
        "Please process the inventory report for the provided customer request.",
        additional_args={
            "customer_request": "I would like to request 100 Sheets of 'A4 paper' (Date of request: 2025-03-01)",
            "current_inventory": inventory_dict
        }
    )
    
    print(result)
