"""Inventory management tools for the inventory agent."""

import pandas as pd
from datetime import datetime
from typing import Dict, Union
from sqlalchemy import create_engine
from smolagents import tool
from .utils import get_all_inventory, get_stock_level, get_supplier_delivery_date

# Database setup
db_engine = create_engine("sqlite:///munder_difflin.db")

@tool
def check_inventory_tool(paper_types: str) -> Dict[str, int]:
    """
    Tool to check inventory levels for specified paper types.

    Args:
        paper_types (str): Comma-separated string of paper types to check.

    Returns:
        Dict[str, int]: A dictionary mapping paper types to their current stock levels.
    """
    # Parse input string into a list of paper types
    types_list = [ptype.strip() for ptype in paper_types.split(",")]

    # Get current inventory snapshot
    inventory_snapshot = get_all_inventory(
        as_of_date=datetime.now().strftime("%Y-%m-%d")
    )

    # Filter inventory for requested paper types
    filtered_inventory = {
        ptype: inventory_snapshot.get(ptype, 0) for ptype in types_list
    }

    return filtered_inventory


@tool
def check_reorder_status_tool(paper_types: str, as_of_date: Union[str, None] = None) -> Dict:
    """
    Tool to check if inventory levels are below minimum stock thresholds for specified items.
    Returns reorder status and recommendations.

    Args:
        paper_types (str): Comma-separated string of paper types to check.
        as_of_date (str, optional): ISO format date to check inventory (defaults to today).

    Returns:
        Dict: Dictionary mapping paper types to their reorder status info:
            - 'current_stock': Current inventory level
            - 'min_stock_level': Minimum threshold
            - 'needs_reorder': Boolean indicating if reorder is needed
            - 'shortage': Quantity below minimum (0 if not needed)
    """
    if as_of_date is None:
        as_of_date = datetime.now().strftime("%Y-%m-%d")
    
    # Parse input string into a list of paper types
    types_list = [ptype.strip() for ptype in paper_types.split(",")]
    
    # Get inventory reference data and current stock levels
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    reorder_status = {}
    
    for ptype in types_list:
        # Find item in inventory database
        item_data = inventory_df[inventory_df["item_name"] == ptype]
        
        if not item_data.empty:
            min_stock = item_data.iloc[0]["min_stock_level"]
            # Get current stock level
            stock_info = get_stock_level(ptype, as_of_date)
            current_stock = stock_info["current_stock"].iloc[0]
            
            shortage = max(0, min_stock - current_stock)
            needs_reorder = current_stock < min_stock
            
            reorder_status[ptype] = {
                "current_stock": int(current_stock),
                "min_stock_level": int(min_stock),
                "needs_reorder": needs_reorder,
                "shortage": int(shortage)
            }
        else:
            reorder_status[ptype] = {
                "error": f"Item '{ptype}' not found in inventory database"
            }
    
    return reorder_status


@tool
def check_delivery_timeline_tool(order_date: str, quantity: int) -> str:
    """
    Tool to check the delivery timeline for an item from the supplier.

    Args:
        order_date (str): The date when the order is placed in ISO format (YYYY-MM-DD).
        quantity (int): The number of units ordered.

    Returns:
        str: Estimated delivery date in ISO format (YYYY-MM-DD).
    """
    return get_supplier_delivery_date(input_date_str=order_date, quantity=quantity)
