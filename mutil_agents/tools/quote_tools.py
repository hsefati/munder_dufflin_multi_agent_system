"""Quote generation and history tools for the quote agent."""

import pandas as pd
import logging
from datetime import datetime
from typing import Dict, List
from sqlalchemy import create_engine
from smolagents import tool
from mutil_agents.tools.utils import search_quote_history

# Configure logging for this module
logger = logging.getLogger(__name__)

# Database setup
db_engine = create_engine("sqlite:///munder_difflin.db")


@tool
def get_quote_history_tool(search_terms: List[str]) -> List[Dict]:
    """
    Retrieves quote history.

    Args:
        search_terms: A list of specific item names to search for (e.g., ["A4 paper"]).
    """
    logger.info(f"Retrieving quote history for search terms: {search_terms}")
    
    # Guard: Ensure we aren't searching for nothing
    if not search_terms or all(not s.strip() for s in search_terms):
        logger.warning("Empty or invalid search terms provided")
        return []

    results = search_quote_history(search_terms=search_terms, limit=5)
    logger.debug(f"Found {len(results)} quote history results")
    return results


@tool
def generate_quote_tool(items: List[str], quantities: List[int]) -> Dict:
    """
    Generates a detailed pricing quote.

    Args:
        items: List of exact item names from available_items.
        quantities: List of integers representing requested amounts.
    """
    logger.info(f"Generating quote for items={items}, quantities={quantities}")
    
    # 1. Guard against empty inputs from the Agent
    if not items or not quantities:
        logger.warning("No items or quantities provided for quote generation")
        return {
            "error": "No items or quantities provided. If inventory is empty, do not call this tool."
        }

    # 2. Guard against mismatched lengths
    if len(items) != len(quantities):
        logger.error(f"Mismatched input: {len(items)} items but {len(quantities)} quantities")
        return {
            "error": f"Mismatched input: You provided {len(items)} items but {len(quantities)} quantities."
        }

    logger.debug("Fetching inventory data for quote generation")
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    quote_items = []
    total_price = 0.0

    for item, qty in zip(items, quantities):
        # Ensure qty is treated as int (Pydantic usually handles this, but safety first)
        try:
            qty = int(qty)
        except (ValueError, TypeError):
            logger.warning(f"Invalid quantity for item {item}: {qty}")
            continue

        item_data = inventory_df[inventory_df["item_name"] == item]
        if not item_data.empty:
            unit_price = item_data.iloc[0]["unit_price"]

            # Discount Logic
            if qty > 1000:
                discount = 0.15
            elif qty > 500:
                discount = 0.10
            elif qty > 100:
                discount = 0.05
            else:
                discount = 0.0

            item_total = (unit_price * (1 - discount)) * qty
            total_price += item_total

            logger.debug(f"Quote item: {item}, qty={qty}, unit_price={unit_price}, discount={discount*100:.0f}%, item_total={item_total:.2f}")
            
            quote_items.append(
                {
                    "item": item,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "discount": f"{discount * 100:.0f}%",
                    "item_total": round(item_total, 2),
                }
            )
        else:
            logger.warning(f"Item '{item}' not found in inventory")

    logger.info(f"Quote generated successfully: {len(quote_items)} items, total_amount=${total_price:.2f}")
    
    return {
        "quote_items": quote_items,
        "total_amount": round(total_price, 2),
        "quote_date": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    # Example usage
    # print(get_quote_history_tool("stapler, printer paper"))
    print(get_quote_history_tool("A4 paper"))
