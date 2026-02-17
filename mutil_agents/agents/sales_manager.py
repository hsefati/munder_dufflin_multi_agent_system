from typing import Dict, List

from smolagents import CodeAgent, OpenAIServerModel, tool

from mutil_agents.config import get_simulation_date, get_simulation_date_str
from mutil_agents.tools.tools import (create_transaction,
                                      generate_financial_report,
                                      get_cash_balance)

# --- Tool Definitions ---


@tool
def finalize_sale(item_name: str, quantity: int, total_price: float) -> str:
    """
    Records a finalized sales transaction in the company database.

    NOTE: If you have multiple items, use 'batch_finalize_sales' instead.

    Args:
        item_name (str): The name of the item being sold.
        quantity (int): The number of units sold.
        total_price (float): The final agreed-upon price (after any discounts).

    Returns:
        str: A confirmation message with the transaction ID.
    """
    try:
        transaction_date = get_simulation_date()

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
def batch_finalize_sales(items: List[Dict[str, any]]) -> str:
    """
    Records MULTIPLE finalized sales transactions in the company database at once.
    This is a BATCH operation - call this once instead of calling finalize_sale multiple times.

    Args:
        items: A list of dictionaries, each containing:
            - 'item_name': str - The name of the item
            - 'quantity': int - The number of units sold
            - 'total_price': float - The final price for this item

    Returns:
        str: A comprehensive report of all sales transactions.

    Example:
        items = [
            {'item_name': 'A4 glossy paper', 'quantity': 200, 'total_price': 180.00},
            {'item_name': 'heavy cardstock', 'quantity': 100, 'total_price': 90.00}
        ]
    """
    transaction_date = get_simulation_date()
    results = []
    transaction_ids = []
    grand_total = 0.0

    for item in items:
        item_name = item["item_name"]
        quantity = item["quantity"]
        total_price = item["total_price"]

        try:
            transaction_id = create_transaction(
                item_name=item_name,
                transaction_type="sales",
                quantity=quantity,
                price=total_price,
                date=transaction_date,
            )

            transaction_ids.append(transaction_id)
            grand_total += total_price

            results.append(
                f"✓ {item_name}: {quantity} units, ${total_price:.2f}, TxID: {transaction_id}"
            )

        except Exception as e:
            results.append(f"✗ {item_name}: ERROR - {str(e)}")

    # Format output
    output = ["=== BATCH SALES REPORT ==="]
    output.extend(results)
    output.append(f"\n**GRAND TOTAL REVENUE: ${grand_total:.2f}**")
    output.append(f"Transaction IDs: {', '.join(map(str, transaction_ids))}")

    return "\n".join(output)


@tool
def check_company_funds() -> str:
    """
    Checks the current liquid cash balance of the company.

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

    Returns:
        str: A detailed, multi-line string summary of the report.
    """
    date_str = get_simulation_date_str()
    report_data = generate_financial_report(date_str)

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
    A specialized agent responsible for finalizing transactions and monitoring finances.
    """

    def __init__(self, model, **kwargs):
        """
        Initializes the Sales & Finance Agent.

        Args:
            model: The language model instance.
            **kwargs: Additional arguments for CodeAgent.
        """
        my_tools = [
            finalize_sale,
            batch_finalize_sales,
            check_company_funds,
            generate_full_report,
        ]

        system_prompt = f"""
You are the Sales & Finance Manager for Beaver's Choice Paper Company.

Current Simulation Date: {get_simulation_date_str()}

Your Goal: Execute approved sales transactions and maintain financial accuracy.

IMPORTANT - BATCH PROCESSING:
When you receive instructions to finalize MULTIPLE items, you MUST use 'batch_finalize_sales'.
DO NOT call 'finalize_sale' in a loop. Use the batch tool for efficiency.

Responsibilities:

FOR SINGLE ITEM:
1. Use 'finalize_sale' to record the transaction
2. Report the transaction ID and confirmation

FOR MULTIPLE ITEMS:
1. Call 'batch_finalize_sales' ONCE with all items and their prices
2. The batch tool will create all transactions and return all IDs
3. Report the consolidated results

RULES:
- You do NOT need customer confirmation (orders are pre-approved by orchestrator)
- Record the EXACT prices provided by the Quoting Agent
- Do not modify or recalculate prices
- Be concise in responses
- If asked about company status, use 'generate_full_report'
"""

        super().__init__(
            tools=my_tools,
            model=model,
            name="sales_finance_manager",
            description="Finalizes approved sales transactions and generates financial reports. Supports batch processing for multiple items.",
            instructions=system_prompt,
            **kwargs,
        )
