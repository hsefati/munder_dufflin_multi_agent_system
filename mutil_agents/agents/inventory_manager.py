import os
import dotenv
import pandas as pd
from smolagents import CodeAgent, tool, OpenAIServerModel
from typing import Dict
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
    # Uses the helper function provided in your starter code
    # We use datetime.now() to get the most current status
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
            # Fallback only if item not in catalog (safety net)
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
def validate_delivery_feasibility(
    item_name: str, quantity: int, customer_deadline: str
) -> str:
    """
    Checks if an order can be fulfilled by the requested deadline, considering current stock
    and supplier delivery times for any missing items.

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


@tool
def get_delivery_estimate(quantity: int, deadline_date: str) -> str:
    """
    Calculates if a restock order of a specific size can arrive before a deadline.

    This tool uses the supplier's standard lead times based on order quantity:
    - <= 10 units: Same day delivery (0 days)
    - 11 - 100 units: Next day delivery (1 day)
    - 101 - 1000 units: 4 days
    - > 1000 units: 7 days

    Args:
        quantity (int): The number of units needed from the supplier.
        deadline_date (str): The customer's requested delivery date (YYYY-MM-DD).

    Returns:
        str: A message indicating if the delivery is 'Feasible' or 'Impossible',
             along with the calculated arrival date.
    """
    sim_date = SIMULATION_DATE

    # 1. Determine Supplier Lead Time based on Quantity
    if quantity <= 10:
        lead_time_days = 0
    elif quantity <= 100:
        lead_time_days = 1
    elif quantity <= 1000:
        lead_time_days = 4
    else:
        lead_time_days = 7

    # 2. Calculate Arrival Date
    supplier_arrival_dt = sim_date + timedelta(days=lead_time_days)

    # 3. Parse Deadline
    try:
        deadline_dt = datetime.strptime(deadline_date, "%Y-%m-%d")
    except ValueError:
        return f"Error: Invalid date format '{deadline_date}'. Please use YYYY-MM-DD."

    # 4. Compare
    arrival_str = supplier_arrival_dt.strftime("%Y-%m-%d")
    if supplier_arrival_dt <= deadline_dt:
        return f"Feasible: Restock can arrive on {arrival_str} (Deadline: {deadline_date})."
    else:
        return f"Impossible: Restock would arrive on {arrival_str}, which is AFTER the deadline of {deadline_date}."


class InventoryManagerAgent(CodeAgent):
    def __init__(self, model, **kwargs):
        """
        Args:
            model: The LLM model instance (e.g., HfApiModel, LiteLLMModel)
            **kwargs: Any additional arguments for the base CodeAgent
        """

        # 1. Define the specific tools this agent needs
        my_tools = [check_stock_level, validate_delivery_feasibility, restock_item]

        # 2. Define the persona/system prompt
        system_prompt = f"""
        You are the Inventory Manager for Beaver's Choice Paper Company.
        Current Date: {get_simulation_date_str()}
        
        Your Goal: Manage stock availability autonomously.
        
        STRICT EXECUTION LOGIC:
        1. **Check**: Always call 'check_stock_level' first.
        
        2. **Analyze**: 
           - If Stock >= Requested: Report "Available".
           - If Stock < Requested: Calculate SHORTAGE = Requested - Stock.
           
        3. **Validate**: Call 'get_delivery_estimate' for the SHORTAGE amount against the deadline.
        
        4. **Action**:
           - If 'get_delivery_estimate' returns "Feasible", you MUST call 'restock_item' for the SHORTAGE amount.
           - If "Impossible", report failure.
           
        5. **Report**:
           - Just state the final status. Do not be chatty.
        """

        # 3. Initialize the parent class with these specific configurations
        super().__init__(
            tools=my_tools,
            model=model,
            name="inventory_manager",
            description="Manages stock and verifies if delivery deadlines can be met.",
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
