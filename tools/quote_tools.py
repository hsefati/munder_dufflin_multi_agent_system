"""Quote generation and history tools for the quote agent."""

import pandas as pd
from datetime import datetime
from typing import Dict, List
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from smolagents import tool
from utils import search_quote_history

# Database setup
db_engine = create_engine("sqlite:///munder_difflin.db")


@tool
def get_quote_history_tool(search_terms: str) -> List[Dict]:
    """
    Tool to retrieve quote history related to a customer's request.

    Args:
        search_terms (str): Comma-separated string of terms to search for in quote explanations.

    Returns:
        List[Dict]: A list of matching quotes, each represented as a dictionary.
    """
    # Parse input string into a list of search terms
    terms_list = [term.strip() for term in search_terms.split(",")]

    # Get quote history for the given search terms
    return search_quote_history(search_terms=terms_list, limit=5)


@tool
def generate_quote_tool(items: str, quantities: str) -> Dict:
    """
    Tool to generate a detailed pricing quote for ordered items.

    Args:
        items (str): Comma-separated list of item names
        quantities (str): Comma-separated list of quantities (must match items)

    Returns:
        Dict: Quote with itemized breakdown, bulk discounts, and total
    """
    # Parse inputs
    item_list = [item.strip() for item in items.split(",")]
    qty_list = [int(qty.strip()) for qty in quantities.split(",")]

    # Get inventory data with unit prices
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)

    quote_items = []
    total_price = 0.0

    for item, qty in zip(item_list, qty_list):
        item_data = inventory_df[inventory_df["item_name"] == item]
        if not item_data.empty:
            unit_price = item_data.iloc[0]["unit_price"]
            # Apply bulk discounts
            if qty > 1000:
                discount = 0.15
            elif qty > 500:
                discount = 0.10
            elif qty > 100:
                discount = 0.05
            else:
                discount = 0.0

            discounted_price = unit_price * (1 - discount)
            item_total = discounted_price * qty
            total_price += item_total

            quote_items.append(
                {
                    "item": item,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "discount": f"{discount * 100:.0f}%",
                    "item_total": item_total,
                }
            )

    return {
        "quote_items": quote_items,
        "total_amount": total_price,
        "quote_date": datetime.now().isoformat(),
    }
