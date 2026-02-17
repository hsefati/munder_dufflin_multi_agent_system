from smolagents import CodeAgent, OpenAIServerModel, tool

# Import shared resources
# We assume the starter code helpers are in 'utils.py'
from mutil_agents.tools.tools import (
    create_transaction,
    get_cash_balance,
    generate_financial_report,
)
from mutil_agents.config import get_simulation_date, get_simulation_date_str

# --- Tool Definitions ---


@tool
def finalize_sale(item_name: str, quantity: int, total_price: float) -> str:
    """
    Records a finalized sales transaction in the company database.

    WARNING: This action is permanent. Only call this tool when the customer has explicitly
    confirmed they want to proceed with the purchase.

    Args:
        item_name (str): The name of the item being sold.
        quantity (int): The number of units sold.
        total_price (float): The final agreed-upon price (after any discounts).

    Returns:
        str: A confirmation message with the transaction ID, or an error message if failed.
    """
    try:
        # We use the simulation date to ensure the record matches the current game time
        transaction_date = get_simulation_date()

        # Call the real database helper
        transaction_id = create_transaction(
            item_name=item_name,
            transaction_type="sales",
            quantity=quantity,
            price=total_price,
            date=transaction_date,
        )

        return (
            f"SUCCESS: Sale recorded. Transaction ID: {transaction_id}\n"
            f"Item: {item_name} | Qty: {quantity} | Total: ${total_price:.2f}"
        )

    except Exception as e:
        return f"ERROR: Failed to record transaction. Details: {str(e)}"


@tool
def check_company_funds() -> str:
    """
    Checks the current liquid cash balance of the company.

    Use this to verify if the company is solvent or to report on financial health.

    Returns:
        str: A formatted string stating the current cash balance.
    """
    date_str = get_simulation_date_str()
    balance = get_cash_balance(date_str)
    return f"Current Cash Balance (as of {date_str}): ${balance:,.2f}"


@tool
def generate_full_report() -> str:
    """
    Generates a comprehensive financial report for the company.

    This includes:
    - Cash balance
    - Total inventory value
    - Top selling products
    - List of current assets

    Returns:
        str: A detailed, multi-line string summary of the report.
    """
    date_str = get_simulation_date_str()
    report_data = generate_financial_report(date_str)

    # Format the dictionary into a readable string for the LLM
    summary = [f"--- Financial Report (As of {date_str}) ---"]
    summary.append(f"Cash Balance: ${report_data['cash_balance']:,.2f}")
    summary.append(f"Inventory Value: ${report_data['inventory_value']:,.2f}")
    summary.append(f"Total Assets: ${report_data['total_assets']:,.2f}")

    summary.append("\nTop Selling Products:")
    for item in report_data.get("top_selling_products", []):
        summary.append(f"- {item['item_name']}: ${item['total_revenue']:,.2f} revenue")

    return "\n".join(summary)


# --- Agent Class ---


class SalesFinanceAgent(CodeAgent):
    """
    A specialized agent responsible for closing deals and monitoring finances.

    Capabilities:
    1. Finalize Sales: Commits orders to the database (Revenue).
    2. Monitor Funds: Checks cash flow.
    3. Reporting: Generates financial summaries.
    """

    def __init__(self, model, **kwargs):
        """
        Initializes the Sales & Finance Agent.

        Args:
            model: The language model instance.
            **kwargs: Additional arguments for CodeAgent.
        """

        my_tools = [finalize_sale, check_company_funds, generate_full_report]

        system_prompt = f"""
        You are the Sales & Finance Manager for Beaver's Choice Paper Company.
        Current Simulation Date: {get_simulation_date_str()}
        
        Your Goal: Secure revenue and ensure financial accuracy.
        
        Responsibilities:
        1. **Closing**: When a customer says "yes" or "buy", use 'finalize_sale'.
        2. **Safety**: NEVER use 'finalize_sale' unless the user has explicitly confirmed the order.
        3. **Health**: If asked about the company's status, use 'generate_full_report'.
        
        Note: You do not calculate prices (Quoting Agent does that). You just record the final agreed numbers.
        """

        super().__init__(
            tools=my_tools,
            model=model,
            name="sales_finance_manager",
            description="Finalizes sales transactions, records orders in the database, and generates financial reports.",
            instructions=system_prompt,
            **kwargs,
        )
