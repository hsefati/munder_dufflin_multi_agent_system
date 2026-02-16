import os
import pandas as pd
import numpy as np
import dotenv
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from smolagents import OpenAIServerModel, CodeAgent, Tool
import logging


# Import existing utilities
from mutil_agents.tools.utils import (
    get_stock_level,
    get_supplier_delivery_date,
    search_quote_history,
    get_cash_balance,
    generate_financial_report,
    get_all_inventory,
)
from mutil_agents.tools.database_setup import create_transaction, init_database


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


dotenv.load_dotenv()
OPENAI_API_KEY = os.getenv("UDACITY_OPENAI_API_KEY")
SMOLAGENT_VERBOSITY = int(os.getenv("SMOLAGENT_VERBOSITY", "0"))
db_engine = create_engine("sqlite:///munder_difflin.db")


model = OpenAIServerModel(
    model_id="gpt-4o-mini",
    api_base="https://openai.vocareum.com/v1",
    api_key=OPENAI_API_KEY,
)


# --- CONFIGURATION CONSTANTS ---
SAFETY_STOCK_Z_SCORE = 1.96  # 95% service level
DEFAULT_LEAD_TIME_DAYS = 7
BULK_DISCOUNT_TIERS = [
    {"min_qty": 100, "discount_pct": 5},
    {"min_qty": 500, "discount_pct": 10},
    {"min_qty": 1000, "discount_pct": 15},
    {"min_qty": 5000, "discount_pct": 20},
]


# --- DATACLASSES FOR STRUCTURED COMMUNICATION ---


@dataclass
class ReorderMetrics:
    """Metrics for inventory reordering decisions."""

    reorder_point: int
    safety_stock: int
    avg_daily_demand: float
    lead_time_days: int
    needs_reorder: bool
    reorder_qty: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FinancialSnapshot:
    """Financial status for transaction feasibility."""

    cash_balance: float
    reorder_cost: float
    can_afford_reorder: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FulfillmentCapability:
    """Order fulfillment capability assessment."""

    stock_sufficient_now: bool
    can_fulfill_after_reorder: bool
    supplier_delivery_date: str
    current_stock: int
    stock_after_reorder: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InventoryAnalysisResult:
    """Complete inventory analysis response from Inventory Expert."""

    status: str
    item_name: str
    current_stock: int
    requested_qty: int
    unit_price: float
    reorder_metrics: ReorderMetrics
    financial: FinancialSnapshot
    fulfillment: FulfillmentCapability
    message: Optional[str] = None
    available_alternatives: Optional[List[str]] = None

    def to_dict(self) -> dict:
        result = asdict(self)
        # Convert nested dataclasses
        if isinstance(self.reorder_metrics, ReorderMetrics):
            result["reorder_metrics"] = self.reorder_metrics.to_dict()
        if isinstance(self.financial, FinancialSnapshot):
            result["financial"] = self.financial.to_dict()
        if isinstance(self.fulfillment, FulfillmentCapability):
            result["fulfillment"] = self.fulfillment.to_dict()
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class PricingDetails:
    """Detailed pricing with discounts."""

    original_unit_price: float
    discounted_unit_price: float
    discount_percentage: float
    total_price: float
    total_savings: float
    tier_info: str
    next_tier: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CustomerHistory:
    """Customer quote history summary."""

    found_quotes: int
    is_repeat_customer: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QuoteResult:
    """Complete quote generation response from Pricing Specialist."""

    status: str
    item_name: str
    quantity: int
    pricing: PricingDetails
    customer_history: CustomerHistory
    message: Optional[str] = None

    def to_dict(self) -> dict:
        result = asdict(self)
        if isinstance(self.pricing, PricingDetails):
            result["pricing"] = self.pricing.to_dict()
        if isinstance(self.customer_history, CustomerHistory):
            result["customer_history"] = self.customer_history.to_dict()
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class TransactionResult:
    """Transaction execution response from Fulfillment Expert."""

    status: str
    transaction_id: Optional[int]
    item_name: str
    transaction_type: str
    quantity: int
    price: float
    date: str
    message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class WorkflowContext:
    """Shared context for multi-agent workflow [web:13]."""

    request: str
    request_date: str
    inventory_result: Optional[InventoryAnalysisResult] = None
    quote_result: Optional[QuoteResult] = None
    fulfillment_results: List[TransactionResult] = field(default_factory=list)
    decisions: List[Dict[str, str]] = field(default_factory=list)

    def add_decision(self, agent: str, decision: str, reason: str):
        """Track decision-making process for debugging."""
        self.decisions.append(
            {
                "timestamp": datetime.now().isoformat(),
                "agent": agent,
                "decision": decision,
                "reason": reason,
            }
        )

    def to_dict(self) -> dict:
        result = asdict(self)
        if self.inventory_result:
            result["inventory_result"] = self.inventory_result.to_dict()
        if self.quote_result:
            result["quote_result"] = self.quote_result.to_dict()
        if self.fulfillment_results:
            result["fulfillment_results"] = [
                fr.to_dict() for fr in self.fulfillment_results
            ]
        return result


# --- HELPER FUNCTIONS ---


def calculate_demand_statistics(item_name: str, days: int = 30) -> Dict[str, float]:
    """Calculate average daily demand and standard deviation from sales history."""
    try:
        query = text("""
            SELECT quantity, date 
            FROM transactions 
            WHERE item_name = :item_name 
            AND transaction_type = 'sales'
            AND date >= date('now', :days_back)
            ORDER BY date DESC
        """)

        df = pd.read_sql(
            query,
            db_engine,
            params={"item_name": item_name, "days_back": f"-{days} days"},
        )

        if df.empty or len(df) < 3:
            return {"avg_daily_demand": 10.0, "std_demand": 5.0, "sample_size": 0}

        df["date"] = pd.to_datetime(df["date"])
        daily_demand = df.groupby(df["date"].dt.date)["quantity"].sum()

        return {
            "avg_daily_demand": float(daily_demand.mean()),
            "std_demand": float(daily_demand.std())
            if len(daily_demand) > 1
            else float(daily_demand.mean() * 0.3),
            "sample_size": len(daily_demand),
        }
    except Exception as e:
        logger.warning(f"Error calculating demand stats for {item_name}: {e}")
        return {"avg_daily_demand": 10.0, "std_demand": 5.0, "sample_size": 0}


def calculate_reorder_point(
    item_name: str, lead_time_days: int = DEFAULT_LEAD_TIME_DAYS
) -> ReorderMetrics:
    """Calculate reorder point and safety stock, returning structured ReorderMetrics."""
    demand_stats = calculate_demand_statistics(item_name)
    safety_stock = (
        SAFETY_STOCK_Z_SCORE * demand_stats["std_demand"] * np.sqrt(lead_time_days)
    )
    reorder_point = (demand_stats["avg_daily_demand"] * lead_time_days) + safety_stock

    return ReorderMetrics(
        reorder_point=round(reorder_point),
        safety_stock=round(safety_stock),
        avg_daily_demand=demand_stats["avg_daily_demand"],
        lead_time_days=lead_time_days,
        needs_reorder=False,  # Will be set by caller
        reorder_qty=0,  # Will be set by caller
    )


def calculate_bulk_discount(quantity: int, unit_price: float) -> PricingDetails:
    """Apply tiered bulk discounts, returning structured PricingDetails."""
    applicable_discount = 0.0
    tier_info = "No bulk discount"

    for tier in sorted(BULK_DISCOUNT_TIERS, key=lambda x: x["min_qty"], reverse=True):
        if quantity >= tier["min_qty"]:
            applicable_discount = tier["discount_pct"]
            tier_info = f"{tier['discount_pct']}% off (bulk {tier['min_qty']}+ units)"
            break

    discount_multiplier = 1 - (applicable_discount / 100)
    discounted_price = unit_price * discount_multiplier
    total_savings = (unit_price - discounted_price) * quantity

    return PricingDetails(
        original_unit_price=unit_price,
        discounted_unit_price=round(discounted_price, 2),
        discount_percentage=applicable_discount,
        total_price=round(discounted_price * quantity, 2),
        total_savings=round(total_savings, 2),
        tier_info=tier_info,
        next_tier=get_next_discount_tier(quantity),
    )


def get_next_discount_tier(current_quantity: int) -> Optional[str]:
    """Suggest next discount tier to encourage upselling."""
    for tier in sorted(BULK_DISCOUNT_TIERS, key=lambda x: x["min_qty"]):
        if current_quantity < tier["min_qty"]:
            additional_needed = tier["min_qty"] - current_quantity
            return f"Buy {additional_needed} more to get {tier['discount_pct']}% off!"
    return None


def calculate_optimal_reorder_quantity(
    item_name: str, current_stock: int, reorder_point: int
) -> int:
    """Calculate optimal reorder quantity."""
    demand_stats = calculate_demand_statistics(item_name)
    optimal_qty = max(
        int(demand_stats["avg_daily_demand"] * 30), reorder_point - current_stock + 100
    )
    return optimal_qty


# --- ENHANCED TOOLS WITH DATACLASS RETURNS ---


class InventoryAnalysisTool(Tool):
    """Enhanced inventory tool returning InventoryAnalysisResult dataclass."""

    name = "inventory_analysis_tool"
    description = """Analyzes inventory with automatic reorder recommendations. 
    Returns InventoryAnalysisResult dataclass as JSON string.
    Use this FIRST for any customer inquiry to check availability."""

    inputs = {
        "item_name": {"type": "string", "description": "Item name to check"},
        "quantity": {"type": "integer", "description": "Requested quantity"},
        "as_of_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
    }
    output_type = "string"

    def forward(self, item_name: str, quantity: int, as_of_date: str) -> str:
        try:
            stock_df = get_stock_level(item_name, as_of_date)
            if stock_df.empty:
                all_items = get_all_inventory(as_of_date)
                result = InventoryAnalysisResult(
                    status="error",
                    item_name=item_name,
                    current_stock=0,
                    requested_qty=quantity,
                    unit_price=0.0,
                    reorder_metrics=ReorderMetrics(0, 0, 0.0, 0, False, 0),
                    financial=FinancialSnapshot(0.0, 0.0, False),
                    fulfillment=FulfillmentCapability(False, False, "N/A", 0, 0),
                    message=f"Item '{item_name}' not found in catalog",
                    available_alternatives=all_items,
                )
                return result.to_json()

            current_stock = int(stock_df["current_stock"].iloc[0])

            price_query = text(
                "SELECT unit_price FROM inventory WHERE item_name = :item_name"
            )
            price_df = pd.read_sql(
                price_query, db_engine, params={"item_name": item_name}
            )

            if price_df.empty:
                result = InventoryAnalysisResult(
                    status="error",
                    item_name=item_name,
                    current_stock=current_stock,
                    requested_qty=quantity,
                    unit_price=0.0,
                    reorder_metrics=ReorderMetrics(0, 0, 0.0, 0, False, 0),
                    financial=FinancialSnapshot(0.0, 0.0, False),
                    fulfillment=FulfillmentCapability(
                        False, False, "N/A", current_stock, current_stock
                    ),
                    message=f"No pricing data found for '{item_name}'",
                )
                return result.to_json()

            unit_price = float(price_df["unit_price"].iloc[0])

            reorder_metrics = calculate_reorder_point(item_name)
            needs_reorder = current_stock <= reorder_metrics.reorder_point
            reorder_qty = (
                calculate_optimal_reorder_quantity(
                    item_name, current_stock, reorder_metrics.reorder_point
                )
                if needs_reorder
                else 0
            )

            # Update reorder metrics
            reorder_metrics.needs_reorder = needs_reorder
            reorder_metrics.reorder_qty = reorder_qty

            cash_balance = get_cash_balance(as_of_date)
            reorder_cost = reorder_qty * unit_price if needs_reorder else 0
            can_afford_reorder = cash_balance >= reorder_cost

            delivery_date = (
                get_supplier_delivery_date(as_of_date, reorder_qty)
                if needs_reorder
                else "N/A"
            )

            stock_sufficient = current_stock >= quantity
            stock_after_reorder = current_stock + reorder_qty
            can_fulfill_after_reorder = stock_after_reorder >= quantity

            result = InventoryAnalysisResult(
                status="success",
                item_name=item_name,
                current_stock=current_stock,
                requested_qty=quantity,
                unit_price=unit_price,
                reorder_metrics=reorder_metrics,
                financial=FinancialSnapshot(
                    cash_balance=cash_balance,
                    reorder_cost=reorder_cost,
                    can_afford_reorder=can_afford_reorder,
                ),
                fulfillment=FulfillmentCapability(
                    stock_sufficient_now=stock_sufficient,
                    can_fulfill_after_reorder=can_fulfill_after_reorder,
                    supplier_delivery_date=delivery_date,
                    current_stock=current_stock,
                    stock_after_reorder=stock_after_reorder,
                ),
            )

            return result.to_json()

        except Exception as e:
            logger.error(f"Error in inventory analysis: {e}")
            error_result = InventoryAnalysisResult(
                status="error",
                item_name=item_name,
                current_stock=0,
                requested_qty=quantity,
                unit_price=0.0,
                reorder_metrics=ReorderMetrics(0, 0, 0.0, 0, False, 0),
                financial=FinancialSnapshot(0.0, 0.0, False),
                fulfillment=FulfillmentCapability(False, False, "N/A", 0, 0),
                message=f"Inventory analysis failed: {str(e)}",
            )
            return error_result.to_json()


class SmartQuotingTool(Tool):
    """Intelligent quoting returning QuoteResult dataclass."""

    name = "smart_quoting_tool"
    description = """Generates quotes with automatic bulk discount application.
    Returns QuoteResult dataclass as JSON string."""

    inputs = {
        "item_name": {"type": "string", "description": "Item name"},
        "quantity": {"type": "integer", "description": "Requested quantity"},
        "unit_price": {"type": "number", "description": "Base unit price"},
        "search_terms": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Keywords for history search",
        },
    }
    output_type = "string"

    def forward(
        self, item_name: str, quantity: int, unit_price: float, search_terms: List[str]
    ) -> str:
        try:
            pricing = calculate_bulk_discount(quantity, unit_price)
            history = search_quote_history(search_terms=search_terms, limit=3)

            result = QuoteResult(
                status="success",
                item_name=item_name,
                quantity=quantity,
                pricing=pricing,
                customer_history=CustomerHistory(
                    found_quotes=len(history) if history else 0,
                    is_repeat_customer=len(history) > 2 if history else False,
                ),
            )

            return result.to_json()

        except Exception as e:
            logger.error(f"Error in smart quoting: {e}")
            error_result = QuoteResult(
                status="error",
                item_name=item_name,
                quantity=quantity,
                pricing=PricingDetails(0.0, 0.0, 0.0, 0.0, 0.0, "", None),
                customer_history=CustomerHistory(0, False),
                message=f"Quote generation failed: {str(e)}",
            )
            return error_result.to_json()


class RobustFulfillmentTool(Tool):
    """Enhanced fulfillment returning TransactionResult dataclass."""

    name = "robust_fulfillment_tool"
    description = """Executes transactions with validation. Returns TransactionResult dataclass as JSON.
    Use 'stock_orders' for purchasing inventory from suppliers.
    Use 'sales' for selling to customers."""

    inputs = {
        "item_name": {"type": "string", "description": "Item name"},
        "transaction_type": {
            "type": "string",
            "description": "'sales' or 'stock_orders'",
        },
        "quantity": {"type": "integer", "description": "Units to transact"},
        "price": {
            "type": "number",
            "description": "Total transaction price (not unit price)",
        },
        "date": {"type": "string", "description": "Transaction date YYYY-MM-DD"},
    }
    output_type = "string"

    def forward(
        self,
        item_name: str,
        transaction_type: str,
        quantity: int,
        price: float,
        date: str,
    ) -> str:
        try:
            if transaction_type not in ["sales", "stock_orders"]:
                result = TransactionResult(
                    status="error",
                    transaction_id=None,
                    item_name=item_name,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    price=price,
                    date=date,
                    message=f"Invalid transaction_type: {transaction_type}. Must be 'sales' or 'stock_orders'.",
                )
                return result.to_json()

            if transaction_type == "sales":
                stock_df = get_stock_level(item_name, date)
                if stock_df.empty:
                    result = TransactionResult(
                        status="error",
                        transaction_id=None,
                        item_name=item_name,
                        transaction_type=transaction_type,
                        quantity=quantity,
                        price=price,
                        date=date,
                        message=f"Cannot sell non-existent item: {item_name}",
                    )
                    return result.to_json()

                current_stock = int(stock_df["current_stock"].iloc[0])
                if current_stock < quantity:
                    result = TransactionResult(
                        status="error",
                        transaction_id=None,
                        item_name=item_name,
                        transaction_type=transaction_type,
                        quantity=quantity,
                        price=price,
                        date=date,
                        message=f"Insufficient stock. Available: {current_stock}, Requested: {quantity}",
                    )
                    return result.to_json()

            transaction_id = create_transaction(
                item_name=item_name,
                transaction_type=transaction_type,
                quantity=quantity,
                price=price,
                date=date,
                db_engine=db_engine,
            )

            result = TransactionResult(
                status="success",
                transaction_id=transaction_id,
                item_name=item_name,
                transaction_type=transaction_type,
                quantity=quantity,
                price=price,
                date=date,
            )

            return result.to_json()

        except Exception as e:
            logger.error(f"Fulfillment error: {e}")
            error_result = TransactionResult(
                status="error",
                transaction_id=None,
                item_name=item_name,
                transaction_type=transaction_type,
                quantity=quantity,
                price=price,
                date=date,
                message=f"Transaction failed: {str(e)}",
            )
            return error_result.to_json()


# --- SPECIALIZED AGENTS ---

inventory_expert = CodeAgent(
    tools=[InventoryAnalysisTool()],
    model=model,
    name="inventory_expert",
    description="Analyzes stock levels, calculates reorder points, returns InventoryAnalysisResult",
    additional_authorized_imports=["json"],
    verbosity_level=SMOLAGENT_VERBOSITY,
)

pricing_specialist = CodeAgent(
    tools=[SmartQuotingTool()],
    model=model,
    name="pricing_specialist",
    description="Generates quotes with bulk discounts, returns QuoteResult",
    additional_authorized_imports=["json"],
    verbosity_level=SMOLAGENT_VERBOSITY,
)

fulfillment_expert = CodeAgent(
    tools=[RobustFulfillmentTool()],
    model=model,
    name="fulfillment_expert",
    description="Executes sales and stock orders, returns TransactionResult",
    additional_authorized_imports=["json"],
    verbosity_level=SMOLAGENT_VERBOSITY,
)

manager = CodeAgent(
    tools=[],
    model=model,
    managed_agents=[inventory_expert, pricing_specialist, fulfillment_expert],
    name="operations_manager",
    description="Coordinates multi-step workflows across inventory, pricing, and fulfillment",
    additional_authorized_imports=["json"],
    verbosity_level=SMOLAGENT_VERBOSITY,
)


# --- ENHANCED WORKFLOW ---


def call_your_multi_agent_system(request_with_date: str) -> Tuple[str, bool, str]:
    """Enhanced multi-agent workflow with structured dataclass communication [web:11]."""
    try:
        prompt = f"""
You are the Operations Manager for Munder Difflin Paper Company.

CUSTOMER REQUEST: {request_with_date}

CRITICAL: All agents now return structured JSON responses that must be parsed with json.loads().

DATA STRUCTURES:
- inventory_expert returns InventoryAnalysisResult with fields: status, item_name, current_stock, requested_qty, unit_price, reorder_metrics, financial, fulfillment
- pricing_specialist returns QuoteResult with fields: status, item_name, quantity, pricing, customer_history
- fulfillment_expert returns TransactionResult with fields: status, transaction_id, item_name, transaction_type, quantity, price, date

YOUR WORKFLOW:

STEP 1 - INVENTORY CHECK:
Call inventory_expert.run() to check stock.
Parse JSON response: inv_data = json.loads(response)
Check inv_data['status'] - if 'error', stop and report the error.
Extract: current_stock, unit_price, reorder_metrics['needs_reorder'], financial['can_afford_reorder'], fulfillment['stock_sufficient_now']

STEP 2 - QUOTE GENERATION:
Call pricing_specialist.run() with unit_price from Step 1.
Parse JSON response: quote_data = json.loads(response)
Extract: pricing['total_price'], pricing['discount_percentage'], pricing['tier_info'], pricing['next_tier']

STEP 3 - FULFILLMENT:
Based on parsed inventory data:
- If fulfillment['stock_sufficient_now'] is True: 
  * Call fulfillment_expert.run() for 'sales' transaction
- If reorder_metrics['needs_reorder'] is True AND financial['can_afford_reorder'] is True:
  * First call fulfillment_expert.run() for 'stock_orders' (use reorder_metrics['reorder_qty'])
  * Then call fulfillment_expert.run() for 'sales'
- Otherwise: skip fulfillment and explain delay

STEP 4 - OUTPUT:
Provide exactly this format:

RESPONSE: [Customer-facing message with price, discounts, delivery info]
FULFILLMENT_STATUS: True or False
DETAILS: [Internal summary of actions taken]

REMEMBER: All tool outputs are JSON strings that MUST be parsed with json.loads() before accessing fields!
"""

        final_response = manager.run(prompt)
        fulfilled = "FULFILLMENT_STATUS: True" in final_response

        if "DETAILS:" in final_response:
            details = final_response.split("DETAILS:")[-1].strip()
        else:
            details = "Workflow completed."

        return final_response, fulfilled, details

    except Exception as e:
        logger.error(f"Critical workflow error: {e}")
        return (f"SYSTEM ERROR: {str(e)}", False, "Workflow failed with exception")


# --- TEST SUITE ---


def run_test_scenarios():
    """Run test scenarios with detailed reporting."""
    try:
        init_database(db_engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database already initialized or error: {e}")

    df = pd.read_csv("quote_requests_sample.csv")
    df["request_date"] = pd.to_datetime(
        df["request_date"], format="%m/%d/%y", errors="coerce"
    )
    df = df.dropna(subset=["request_date"]).sort_values("request_date")

    results = []

    print("\n" + "=" * 80)
    print("MUNDER DIFFLIN MULTI-AGENT SYSTEM - ENHANCED WITH DATACLASSES")
    print("=" * 80 + "\n")

    cnt = 0
    for idx, row in df.head(5).iterrows():
        req_date = row["request_date"].strftime("%Y-%m-%d")

        print(f"\n{'─' * 80}")
        print(f"TEST CASE #{idx + 1}")
        print(f"{'─' * 80}")
        print(f"Request: {row['request']}")
        print(f"Date: {req_date}")
        print()

        response, fulfilled, details = call_your_multi_agent_system(
            f"{row['request']} (Date: {req_date})"
        )

        report = generate_financial_report(req_date)

        print(f"Fulfillment Status: {'✓ SUCCESS' if fulfilled else '✗ FAILED'}")
        print(f"Cash Balance: ${report['cash_balance']:,.2f}")
        print(f"Inventory Value: ${report['inventory_value']:,.2f}")
        print(f"Total Assets: ${report['total_assets']:,.2f}")

        response_str = str(response) if response else "No response"
        if "RESPONSE:" in response_str:
            customer_msg = (
                response_str.split("RESPONSE:")[-1]
                .split("FULFILLMENT_STATUS:")[0]
                .strip()
            )
        else:
            customer_msg = (
                response_str[:200] if len(response_str) > 200 else response_str
            )

        details_str = str(details) if details else "No details"
        details_preview = details_str[:300] if len(details_str) > 300 else details_str

        print(f"\nCustomer Response:\n{customer_msg}")
        print(f"\nInternal Details:\n{details_preview}")

        results.append(
            {
                "request_id": idx + 1,
                "request": row["request"],
                "request_date": req_date,
                "cash_balance": report["cash_balance"],
                "inventory_value": report["inventory_value"],
                "total_assets": report["total_assets"],
                "fulfilled": fulfilled,
                "fulfillment_details": details_str,
                "customer_response": response_str,
            }
        )

        cnt += 1
        if cnt >= 5:
            logger.info("Reached maximum test count (5). Stopping test execution.")
            break
        break

    results_df = pd.DataFrame(results)
    results_df.to_csv("test_results_dataclass_enhanced.csv", index=False)

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {len(results)}")
    print(f"Successful: {sum(r['fulfilled'] for r in results)}")
    print(f"Failed: {sum(not r['fulfilled'] for r in results)}")
    print(f"Final Cash: ${results[-1]['cash_balance']:,.2f}")
    print(f"Final Inventory: ${results[-1]['inventory_value']:,.2f}")
    print(f"Final Total Assets: ${results[-1]['total_assets']:,.2f}")
    print(f"\nDetailed results saved to: test_results_dataclass_enhanced.csv")
    print("=" * 80 + "\n")

    return results


if __name__ == "__main__":
    results = run_test_scenarios()
