"""Order fulfillment tools for the fulfillment agent."""

import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Union
from sqlalchemy import create_engine
from smolagents import tool
from mutil_agents.tools.database_setup import create_transaction
from mutil_agents.tools.utils import get_stock_level, get_supplier_delivery_date

# Configure logging for this module
logger = logging.getLogger(__name__)

# Database setup
db_engine = create_engine("sqlite:///munder_difflin.db")


# Wrapper function for create_transaction to include db_engine
def _create_transaction_wrapper(
    item_name: str,
    transaction_type: str,
    quantity: int,
    price: float,
    date: Union[str, datetime],
) -> int:
    """Wrapper that passes db_engine to the imported create_transaction function."""
    return create_transaction(
        item_name, transaction_type, quantity, price, date, db_engine
    )


@tool
def create_order_fulfillment_tool(
    item_name: str, quantity: int, price_per_unit: float, transaction_date: str
) -> Dict:
    """
    Tool to complete order fulfillment by recording a sales transaction in the database.

    Args:
        item_name (str): Name of the item being sold.
        quantity (int): Number of units sold.
        price_per_unit (float): Price per unit.
        transaction_date (str): Date of transaction in ISO format (YYYY-MM-DD).

    Returns:
        Dict: Transaction confirmation with:
            - 'transaction_id': ID of the recorded transaction
            - 'item_name': Item sold
            - 'quantity': Units sold
            - 'total_price': Total transaction amount
            - 'status': 'success' or 'error'
            - 'message': Confirmation or error message
    """
    logger.info(
        f"Processing order fulfillment for item={item_name}, quantity={quantity}, price_per_unit={price_per_unit}"
    )
    try:
        total_price = quantity * price_per_unit

        # Verify item exists and sufficient stock is available
        logger.debug(f"Checking stock level for {item_name} as of {transaction_date}")
        stock_info = get_stock_level(item_name, transaction_date)
        current_stock = stock_info["current_stock"].iloc[0]

        if current_stock < quantity:
            logger.warning(
                f"Insufficient stock for {item_name}: available={int(current_stock)}, requested={quantity}"
            )
            return {
                "status": "error",
                "message": f"Insufficient stock. Available: {int(current_stock)}, Requested: {quantity}",
                "transaction_id": "N/A",
            }

        # Create the sales transaction
        logger.debug(f"Creating sales transaction for {item_name}")
        transaction_id = _create_transaction_wrapper(
            item_name=item_name,
            transaction_type="sales",
            quantity=quantity,
            price=total_price,
            date=transaction_date,
        )

        logger.info(
            f"Order fulfillment completed successfully: transaction_id={transaction_id}, item={item_name}, qty={quantity}"
        )
        return {
            "transaction_id": str(transaction_id),
            "item_name": item_name,
            "quantity": quantity,
            "total_price": str(total_price),
            "status": "success",
            "message": f"Order fulfillment completed. Transaction ID: {transaction_id}",
        }
    except Exception as e:
        logger.error(
            f"Fulfillment failed for item={item_name}: {str(e)}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Fulfillment failed: {str(e)}",
            "transaction_id": "N/A",
        }


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
    logger.info(
        f"Checking delivery timeline for order_date={order_date}, quantity={quantity}"
    )
    delivery_date = get_supplier_delivery_date(
        input_date_str=order_date, quantity=quantity
    )
    logger.debug(f"Estimated delivery date: {delivery_date}")
    return delivery_date


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,  # Set to DEBUG, INFO, WARNING, ERROR, or CRITICAL
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("munder_difflin.log"),  # Log to file
            logging.StreamHandler(),  # Also log to console
        ],
    )

    quoted_item = {
        "Paper plates": {
            "item_name": "Paper plates",
            "quantity": 748,
            "price_per_unit": 0.1,
            "transaction_date": "2025-12-31",
        }
    }
    create_order_fulfillment_tool(**quoted_item["Paper plates"])
