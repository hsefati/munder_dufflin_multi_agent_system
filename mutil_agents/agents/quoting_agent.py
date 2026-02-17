from datetime import datetime
from typing import Dict, List

import pandas as pd
from smolagents import CodeAgent, tool
from sqlalchemy import create_engine

from mutil_agents.config import get_simulation_date_str
from mutil_agents.tools.tools import search_quote_history

db_engine = create_engine("sqlite:///munder_difflin.db")


@tool
def check_price_catalog(item_name: str) -> float:
    """
    Retrieves the current base unit price for a specific item from the system database.

    NOTE: If you have multiple items, use 'batch_calculate_quotes' instead.

    Args:
        item_name (str): The exact name of the item to look up.

    Returns:
        float: The unit price of the item. Returns 0.0 if the item is not found.
    """
    query = "SELECT unit_price FROM inventory WHERE item_name = :item_name"
    try:
        df = pd.read_sql(query, db_engine, params={"item_name": item_name})
        if df.empty:
            return 0.0
        return float(df.iloc[0]["unit_price"])
    except Exception as e:
        print(f"Error checking price catalog: {e}")
        return 0.0


@tool
def get_quote_history_summary(item_name: str) -> str:
    """
    Retrieves a summary of historical quotes for a specific item.

    Args:
        item_name (str): The keyword or item name to search for.

    Returns:
        str: A formatted string summarizing the most recent relevant quotes.
    """
    results = search_quote_history([item_name], limit=3)
    if not results:
        return "No historical quotes found for comparison."

    summary = "--- Historical Quote Benchmarks ---\n"
    for q in results:
        date = q.get("order_date", "Unknown Date")
        size = q.get("order_size", "N/A")
        total = q.get("total_amount", 0.0)
        note = q.get("quote_explanation", "No explanation")
        summary += f"- [{date}] Size: {size} | Total: ${total} | Note: {note}\n"

    return summary


@tool
def calculate_quote(item_name: str, quantity: int) -> str:
    """
    Calculates a final price quote for a single item with automatic bulk discounts.

    NOTE: If you have multiple items, use 'batch_calculate_quotes' instead.

    Discount tiers:
    - Standard Tier (< 100 units): Base Price
    - Volume Tier (100 - 999 units): 10% Discount
    - Bulk Tier (1000+ units): 20% Discount

    Args:
        item_name (str): The name of the product to quote.
        quantity (int): The number of units.

    Returns:
        str: A detailed breakdown of the quote.
    """
    unit_price = check_price_catalog(item_name)
    if unit_price == 0.0:
        return f"Error: Item '{item_name}' was not found in the price catalog."

    subtotal = unit_price * quantity

    # Apply Discount Logic
    discount_rate = 0.0
    reason = "Standard Retail Price"

    if quantity >= 1000:
        discount_rate = 0.20
        reason = "Bulk Tier (20% off)"
    elif quantity >= 100:
        discount_rate = 0.10
        reason = "Volume Tier (10% off)"

    discount_amount = subtotal * discount_rate
    final_total = subtotal - discount_amount

    return (
        f"--- QUOTE GENERATED ---\n"
        f"Item: {item_name}\n"
        f"Quantity: {quantity}\n"
        f"Unit Price: ${unit_price:.2f}\n"
        f"Subtotal: ${subtotal:.2f}\n"
        f"Discount: -${discount_amount:.2f} ({reason})\n"
        f"**Total Price: ${final_total:.2f}**"
    )


@tool
def batch_calculate_quotes(items: List[Dict[str, any]]) -> str:
    """
    Calculates price quotes for MULTIPLE items at once with automatic bulk discounts.
    This is a BATCH operation - call this once instead of calling calculate_quote multiple times.

    Discount tiers apply PER ITEM:
    - Standard Tier (< 100 units): Base Price
    - Volume Tier (100 - 999 units): 10% Discount
    - Bulk Tier (1000+ units): 20% Discount

    Args:
        items: A list of dictionaries, each containing:
            - 'item_name': str - The name of the product
            - 'quantity': int - The number of units

    Returns:
        str: A comprehensive quote report for ALL items including grand total.

    Example:
        items = [
            {'item_name': 'A4 glossy paper', 'quantity': 200},
            {'item_name': 'heavy cardstock', 'quantity': 100}
        ]
    """
    results = []
    grand_total = 0.0
    all_valid = True

    for item in items:
        item_name = item["item_name"]
        quantity = item["quantity"]

        # Get unit price
        query = "SELECT unit_price FROM inventory WHERE item_name = :item_name"
        try:
            df = pd.read_sql(query, db_engine, params={"item_name": item_name})
            if df.empty:
                results.append(
                    {
                        "item_name": item_name,
                        "quantity": quantity,
                        "status": "ERROR",
                        "message": f"Item '{item_name}' not found in catalog",
                        "total_price": 0.0,
                    }
                )
                all_valid = False
                continue

            unit_price = float(df.iloc[0]["unit_price"])
        except Exception as e:
            results.append(
                {
                    "item_name": item_name,
                    "quantity": quantity,
                    "status": "ERROR",
                    "message": f"Database error: {str(e)}",
                    "total_price": 0.0,
                }
            )
            all_valid = False
            continue

        # Calculate pricing
        subtotal = unit_price * quantity

        # Apply discount logic per item
        discount_rate = 0.0
        tier = "Standard"

        if quantity >= 1000:
            discount_rate = 0.20
            tier = "Bulk (20% off)"
        elif quantity >= 100:
            discount_rate = 0.10
            tier = "Volume (10% off)"

        discount_amount = subtotal * discount_rate
        final_total = subtotal - discount_amount
        grand_total += final_total

        results.append(
            {
                "item_name": item_name,
                "quantity": quantity,
                "status": "SUCCESS",
                "unit_price": unit_price,
                "subtotal": subtotal,
                "discount_rate": discount_rate,
                "discount_amount": discount_amount,
                "tier": tier,
                "total_price": final_total,
            }
        )

    # Format output
    output = ["=== BATCH QUOTE REPORT ===\n"]

    for r in results:
        output.append(f"Item: {r['item_name']}")
        output.append(f"  Quantity: {r['quantity']}")

        if r["status"] == "ERROR":
            output.append(f"  Status: ERROR - {r['message']}")
        else:
            output.append(f"  Unit Price: ${r['unit_price']:.2f}")
            output.append(f"  Subtotal: ${r['subtotal']:.2f}")
            output.append(f"  Discount: -${r['discount_amount']:.2f} ({r['tier']})")
            output.append(f"  Total: ${r['total_price']:.2f}")
        output.append("")

    if all_valid:
        output.append(f"**GRAND TOTAL: ${grand_total:.2f}**")
    else:
        output.append(f"**PARTIAL TOTAL (some items failed): ${grand_total:.2f}**")

    return "\n".join(output)


# --- Agent Class ---


class QuotingSpecialistAgent(CodeAgent):
    def __init__(self, model, **kwargs):
        # Include batch tool
        my_tools = [
            check_price_catalog,
            get_quote_history_summary,
            calculate_quote,
            batch_calculate_quotes,
        ]

        system_prompt = f"""
You are the Quoting Specialist for Beaver's Choice Paper Company.

Simulation Date: {get_simulation_date_str()}

Your Goal: Provide accurate pricing based on the REAL database catalog.

IMPORTANT - BATCH PROCESSING:
When you receive requests for MULTIPLE items, you MUST use 'batch_calculate_quotes'.
DO NOT call 'calculate_quote' in a loop. Use the batch tool for efficiency.

Instructions:

FOR SINGLE ITEM:
1. Use 'calculate_quote' to generate the price
2. If price is 0.0 or item not found, report error

FOR MULTIPLE ITEMS:
1. Call 'batch_calculate_quotes' ONCE with all items
2. The batch tool will return individual prices AND a grand total
3. Report the complete batch quote

RULES:
- Always query the live database for prices
- Apply bulk discounts automatically (per item)
- Use 'get_quote_history_summary' only if explicitly asked for comparisons
- Be concise in responses
"""

        super().__init__(
            tools=my_tools,
            model=model,
            name="quoting_specialist",
            description="Accesses the database to get real prices and calculates bulk discounts. Supports batch processing for multiple items.",
            instructions=system_prompt,
            **kwargs,
        )
