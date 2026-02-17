from smolagents import CodeAgent, tool
import pandas as pd
from datetime import datetime

from sqlalchemy import create_engine

from mutil_agents.tools.tools import search_quote_history

from mutil_agents.config import get_simulation_date_str

db_engine = create_engine("sqlite:///munder_difflin.db")


@tool
def check_price_catalog(item_name: str) -> float:
    """
    Retrieves the current base unit price for a specific item from the system database.

    This tool queries the live 'inventory' table to find the standard retail price
    before any discounts are applied.

    Args:
        item_name (str): The exact name of the item to look up (e.g., 'A4 glossy paper', 'heavy cardstock').

    Returns:
        float: The unit price of the item. Returns 0.0 if the item is not found in the catalog.
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

    Use this tool when a customer asks for a better price, a comparison, or if you need
    to see what was charged for similar orders in the past. It helps ensure pricing consistency.

    Args:
        item_name (str): The keyword or item name to search for in the quote history (e.g., 'glossy paper').

    Returns:
        str: A formatted string summarizing the most recent relevant quotes, including
             order size, total amount, and any explanations (like discounts given).
             Returns "No historical quotes found" if no records match.
    """
    # Uses the helper function from utils.py
    results = search_quote_history([item_name], limit=3)

    if not results:
        return "No historical quotes found for comparison."

    summary = "--- Historical Quote Benchmarks ---\n"
    for q in results:
        # data is expected to be a list of dicts from the helper
        date = q.get("order_date", "Unknown Date")
        size = q.get("order_size", "N/A")
        total = q.get("total_amount", 0.0)
        note = q.get("quote_explanation", "No explanation")

        summary += f"- [{date}] Size: {size} | Total: ${total} | Note: {note}\n"
    return summary


@tool
def calculate_quote(item_name: str, quantity: int) -> str:
    """
    Calculates a final price quote for a customer order, automatically applying bulk discounts.

    This is the PRIMARY tool for pricing. It looks up the base price and applies the following logic:
    - Standard Tier (< 100 units): Base Price.
    - Volume Tier (100 - 999 units): 10% Discount.
    - Bulk Tier (1000+ units): 20% Discount.

    Args:
        item_name (str): The name of the product to quote.
        quantity (int): The number of units the customer wants to buy.

    Returns:
        str: A detailed breakdown of the quote, including the unit price, subtotal,
             discount applied (if any), and the final total price.
    """
    # 1. Get the real price
    unit_price = check_price_catalog(item_name)

    if unit_price == 0.0:
        return f"Error: Item '{item_name}' was not found in the price catalog."

    subtotal = unit_price * quantity

    # 2. Apply Discount Logic
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


# --- Agent Class ---


class QuotingSpecialistAgent(CodeAgent):
    def __init__(self, model, **kwargs):

        my_tools = [check_price_catalog, get_quote_history_summary, calculate_quote]

        system_prompt = f"""
        You are the Quoting Specialist for Beaver's Choice Paper Company.
        Simulation Date: {get_simulation_date_str()}
        
        Your Goal: Provide accurate pricing based on the REAL database catalog.
        
        Instructions:
        1. Always use 'calculate_quote' to generate the price. This tool queries the live database.
        2. If the price comes back as 0.0 or the item is not found, inform the Orchestrator that the item is not in our catalog.
        3. Use 'get_quote_history_summary' if the user asks for a price comparison or negotiation.
        """

        super().__init__(
            tools=my_tools,
            model=model,
            name="quoting_specialist",
            description="Accesses the database to get real prices and calculates bulk discounts.",
            instructions=system_prompt,
            **kwargs,
        )
