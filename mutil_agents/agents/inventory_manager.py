import os
import dotenv
import pandas as pd
from smolagents import CodeAgent, tool, OpenAIServerModel
from typing import Dict, List
from datetime import datetime, timedelta
from sqlalchemy import create_engine

from mutil_agents.config import (
    SIMULATION_DATE,
    get_simulation_date_str,
    get_simulation_date,
)

from mutil_agents.tools.tools import (
    get_stock_level,
    get_all_inventory,
    get_supplier_delivery_date,
    create_transaction,
)


@tool
def check_stock_level(item_name: str) -> int:
    """
    Checks the current quantity of a specific item in the warehouse.

    Args:
        item_name: The name of the paper product to check (e.g., 'Glossy Paper').
    """
    result_df = get_stock_level(item_name, SIMULATION_DATE.isoformat())
    if result_df.empty:
        return 0
    return int(result_df["current_stock"].iloc[0])


@tool
def check_global_inventory() -> Dict[str, int]:
    """
    Retrieves a snapshot of ALL items currently in stock.
    Useful for seeing what is available without asking for a specific item.
    """
    return get_all_inventory(SIMULATION_DATE.isoformat())


db_engine = create_engine("sqlite:///munder_difflin.db")


@tool
def restock_item(item_name: str, quantity: int) -> str:
    """
    Places a 'stock_orders' transaction to replenish inventory.
    Automatically looks up the correct unit cost from the 'inventory' table.

    Args:
        item_name (str): The item to order.
        quantity (int): The amount to order.
    """
    # 1. Fetch the real unit cost from the database
    try:
        query = "SELECT unit_price FROM inventory WHERE item_name = :item_name"
        df = pd.read_sql(query, db_engine, params={"item_name": item_name})
        if not df.empty:
            unit_cost = float(df.iloc[0]["unit_price"])
        else:
            unit_cost = 1.0
            print(
                f"Warning: Item '{item_name}' not in catalog. Using default cost $1.00"
            )

    except Exception as e:
        return f"Error fetching price: {str(e)}"

    # 2. Create the Transaction
    total_cost = unit_cost * quantity
    tid = create_transaction(
        item_name=item_name,
        transaction_type="stock_orders",
        quantity=quantity,
        price=total_cost,
        date=get_simulation_date(),
    )

    return f"SUCCESS: Restock ordered. Item: {item_name} | Qty: {quantity} | Cost: ${total_cost:.2f} | TxID: {tid}"


@tool
def batch_validate_delivery_feasibility(items: List[Dict[str, any]]) -> str:
    """
    Checks if multiple items can be fulfilled by their requested deadlines.
    This is a BATCH operation - call this once for all items instead of calling
    validate_delivery_feasibility multiple times.

    Args:
        items: A list of dictionaries, each containing:
            - 'item_name': str - The name of the item
            - 'quantity': int - The requested quantity
            - 'deadline': str - The deadline in YYYY-MM-DD format

    Returns:
        str: A comprehensive report on the feasibility of ALL items.

    Example:
        items = [
            {'item_name': 'A4 glossy paper', 'quantity': 200, 'deadline': '2025-04-15'},
            {'item_name': 'heavy cardstock', 'quantity': 100, 'deadline': '2025-04-15'}
        ]
    """
    current_date = SIMULATION_DATE
    results = []

    for item in items:
        item_name = item["item_name"]
        quantity = item["quantity"]
        customer_deadline = item["deadline"]

        # 1. Check local stock
        stock_df = get_stock_level(item_name, current_date)
        current_stock = (
            int(stock_df["current_stock"].iloc[0]) if not stock_df.empty else 0
        )

        if current_stock >= quantity:
            results.append(
                {
                    "item_name": item_name,
                    "quantity": quantity,
                    "deadline": customer_deadline,
                    "status": "FEASIBLE",
                    "reason": f"Sufficient stock ({current_stock} units available)",
                    "current_stock": current_stock,
                    "needs_restock": False,
                    "restock_qty": 0,
                }
            )
            continue

        # 2. Calculate shortage and supplier timeline
        shortage = quantity - current_stock
        supplier_arrival = get_supplier_delivery_date(
            current_date.isoformat(), shortage
        )

        # 3. Compare dates
        supplier_dt = datetime.fromisoformat(supplier_arrival)
        deadline_dt = datetime.fromisoformat(customer_deadline)

        if supplier_dt <= deadline_dt:
            results.append(
                {
                    "item_name": item_name,
                    "quantity": quantity,
                    "deadline": customer_deadline,
                    "status": "FEASIBLE",
                    "reason": f"Stock low ({current_stock}), restock of {shortage} units arrives {supplier_arrival}",
                    "current_stock": current_stock,
                    "needs_restock": True,
                    "restock_qty": shortage,
                    "restock_arrival": supplier_arrival,
                }
            )
        else:
            results.append(
                {
                    "item_name": item_name,
                    "quantity": quantity,
                    "deadline": customer_deadline,
                    "status": "IMPOSSIBLE",
                    "reason": f"Short {shortage} units. Supplier arrival {supplier_arrival} is AFTER deadline {customer_deadline}",
                    "current_stock": current_stock,
                    "needs_restock": False,
                    "restock_qty": 0,
                }
            )

    # Format results
    output = ["=== BATCH DELIVERY FEASIBILITY REPORT ==="]

    all_feasible = all(r["status"] == "FEASIBLE" for r in results)
    output.append(
        f"Overall Status: {'ALL FEASIBLE' if all_feasible else 'SOME IMPOSSIBLE'}"
    )
    for r in results:
        output.append(f"\nItem: {r['item_name']}")
        output.append(f"  Quantity: {r['quantity']}")
        output.append(f"  Deadline: {r['deadline']}")
        output.append(f"  Status: {r['status']}")
        output.append(f"  Reason: {r['reason']}")
        if r["needs_restock"]:
            output.append(f"  ACTION REQUIRED: Restock {r['restock_qty']} units")

    return "\n".join(output)


@tool
def batch_restock_items(items: List[Dict[str, any]]) -> str:
    """
    Places restock orders for multiple items at once.
    This is a BATCH operation - call this once instead of calling restock_item multiple times.

    Args:
        items: A list of dictionaries, each containing:
            - 'item_name': str - The name of the item
            - 'quantity': int - The amount to restock

    Returns:
        str: A summary of all restock orders placed.

    Example:
        items = [
            {'item_name': 'A4 glossy paper', 'quantity': 50},
            {'item_name': 'heavy cardstock', 'quantity': 100}
        ]
    """
    results = []

    for item in items:
        item_name = item["item_name"]
        quantity = item["quantity"]

        # Fetch the real unit cost from the database
        try:
            query = "SELECT unit_price FROM inventory WHERE item_name = :item_name"
            df = pd.read_sql(query, db_engine, params={"item_name": item_name})
            if not df.empty:
                unit_cost = float(df.iloc[0]["unit_price"])
            else:
                unit_cost = 1.0
                results.append(
                    f"WARNING: {item_name} not in catalog, using default cost"
                )

        except Exception as e:
            results.append(f"ERROR: {item_name} - {str(e)}")
            continue

        # Create the Transaction
        total_cost = unit_cost * quantity
        tid = create_transaction(
            item_name=item_name,
            transaction_type="stock_orders",
            quantity=quantity,
            price=total_cost,
            date=get_simulation_date(),
        )

        results.append(
            f"✓ {item_name}: {quantity} units ordered, Cost: ${total_cost:.2f}, TxID: {tid}"
        )

    output = ["=== BATCH RESTOCK REPORT ==="]
    output.extend(results)
    return "\n".join(output)


@tool
def validate_delivery_feasibility(
    item_name: str, quantity: int, customer_deadline: str
) -> str:
    """
    Checks if an order can be fulfilled by the requested deadline, considering current stock
    and supplier delivery times for any missing items.

    NOTE: If you have multiple items, use 'batch_validate_delivery_feasibility' instead.

    Args:
        item_name: The name of the item.
        quantity: The total amount requested.
        customer_deadline: The date the customer needs it by (YYYY-MM-DD).
    """
    current_date = SIMULATION_DATE
    # 1. Check local stock
    stock_df = get_stock_level(item_name, current_date)
    current_stock = int(stock_df["current_stock"].iloc[0]) if not stock_df.empty else 0

    if current_stock >= quantity:
        return (
            f"Feasible: We have sufficient stock ({current_stock}) to ship immediately."
        )

    # 2. Calculate shortage and supplier timeline
    shortage = quantity - current_stock
    supplier_arrival = get_supplier_delivery_date(current_date.isoformat(), shortage)

    # 3. Compare dates
    supplier_dt = datetime.fromisoformat(supplier_arrival)
    deadline_dt = datetime.fromisoformat(customer_deadline)

    if supplier_dt <= deadline_dt:
        return (
            f"Feasible: Stock low ({current_stock}), but we can restock {shortage} units "
            f"by {supplier_arrival}, which meets the deadline of {customer_deadline}."
        )

    else:
        return (
            f"Impossible: We are short {shortage} units. Supplier delivery would arrive on "
            f"{supplier_arrival}, which is AFTER the deadline of {customer_deadline}."
        )


class InventoryManagerAgent(CodeAgent):
    def __init__(self, model, **kwargs):
        """
        Args:
            model: The LLM model instance (e.g., HfApiModel, LiteLLMModel)
            **kwargs: Any additional arguments for the base CodeAgent
        """
        # 1. Define the specific tools this agent needs - NOW WITH BATCH TOOLS
        my_tools = [
            check_stock_level,
            validate_delivery_feasibility,
            restock_item,
            batch_validate_delivery_feasibility,
            batch_restock_items,
        ]

        # 2. Define the persona/system prompt
        system_prompt = f"""
You are the Inventory Manager for Beaver's Choice Paper Company.

Current Date: {get_simulation_date_str()}

Your Goal: Manage stock availability autonomously and efficiently.

IMPORTANT - BATCH PROCESSING:
When you receive requests for MULTIPLE items, you MUST use the batch tools:
- Use 'batch_validate_delivery_feasibility' for checking multiple items at once
- Use 'batch_restock_items' for restocking multiple items at once

DO NOT call single-item tools in a loop. Use batch tools for efficiency.

EXECUTION LOGIC:

FOR SINGLE ITEM REQUESTS:
1. Call 'check_stock_level' or 'validate_delivery_feasibility'
2. If restock needed and feasible, call 'restock_item'
3. Report status

FOR MULTIPLE ITEM REQUESTS:
1. Call 'batch_validate_delivery_feasibility' ONCE with all items
2. Parse the batch report to identify which items need restocking
3. Call 'batch_restock_items' ONCE with all items that need restocking
4. Report consolidated status

RULES:
- Be concise in your responses
- If any item is IMPOSSIBLE to fulfill, report it clearly
- Only restock items that are marked as needing restock in the feasibility report
"""

        # 3. Initialize the parent class with these specific configurations
        super().__init__(
            tools=my_tools,
            model=model,
            name="inventory_manager",
            description="Manages stock and verifies if delivery deadlines can be met. Supports batch processing for multiple items.",
            instructions=system_prompt,
            **kwargs,
        )


if __name__ == "__main__":
    dotenv.load_dotenv()
    OPENAI_API_KEY = os.getenv("UDACITY_OPENAI_API_KEY")
    SMOLAGENT_VERBOSITY = int(os.getenv("SMOLAGENT_VERBOSITY", "0"))
    LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")

    model = OpenAIServerModel(
        model_id="gpt-4o-mini",
        api_base="https://openai.vocareum.com/v1",
        api_key=OPENAI_API_KEY,
    )

    inventory_manager = InventoryManagerAgent(
        model=model, verbosity_level=SMOLAGENT_VERBOSITY
    )

    res = inventory_manager.run(
        """I would like to order 1000 of 'A4 paper' by April 15, 2025"""
    )
    print(res)
