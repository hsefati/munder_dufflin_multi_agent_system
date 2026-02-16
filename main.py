import time
import pandas as pd
import os
import dotenv
from sqlalchemy import create_engine
from smolagents import (
    OpenAIServerModel,
)
import logging
from mutil_agents.tools.database_setup import init_database

# from mutil_agents.agents.inventory_agent import InventoryCheckerAgent
# from mutil_agents.agents.inventory_management import InventoryManagerAgent
from mutil_agents.agents.inventory_management_v2 import InventoryManagerAgent

# from mutil_agents.agents.quote_agent import QuoteAgent
from mutil_agents.agents.quote_agent_v2 import QuoteAgent
from mutil_agents.agents.customer_agent import CustomerAgent

# from mutil_agents.agents.fulfillment_agent import FulfillmentAgent
from mutil_agents.agents.fulfillment_agent_v2 import FulfillmentAgent
from mutil_agents.agents.orchestrator_agent import OrchestratorAgent
from mutil_agents.tools.utils import generate_financial_report

dotenv.load_dotenv()
OPENAI_API_KEY = os.getenv("UDACITY_OPENAI_API_KEY")
SMOLAGENT_VERBOSITY = int(os.getenv("SMOLAGENT_VERBOSITY", "0"))
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")  # Default to INFO level

if LOGGING_LEVEL.upper() == "DEBUG":
    logging_level = logging.DEBUG
elif LOGGING_LEVEL.upper() == "INFO":
    logging_level = logging.INFO
elif LOGGING_LEVEL.upper() == "WARNING":
    logging_level = logging.WARNING
elif LOGGING_LEVEL.upper() == "ERROR":
    logging_level = logging.ERROR
elif LOGGING_LEVEL.upper() == "CRITICAL":
    logging_level = logging.CRITICAL
else:
    logging_level = logging.INFO  # Default to INFO if invalid level provided

model = OpenAIServerModel(
    model_id="gpt-4o-mini",
    api_base="https://openai.vocareum.com/v1",
    api_key=OPENAI_API_KEY,
)


# Configure logging at the module level
logging.basicConfig(
    level=logging_level,  # Set to DEBUG, INFO, WARNING, ERROR, or CRITICAL
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("munder_difflin.log"),  # Log to file
        logging.StreamHandler(),  # Also log to console
    ],
)

# Create an SQLite database
db_engine = create_engine("sqlite:///munder_difflin.db")


def run_test_scenarios():

    # Check if database is already initialized
    try:
        existing_tables = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table'", db_engine
        )
        if len(existing_tables) > 0 and "inventory" in existing_tables["name"].values:
            print("Database already initialized. Skipping initialization...")
        else:
            print("Initializing Database...")
            init_database(db_engine)
    except Exception as e:
        print(f"Checking database status: {e}")
        print("Initializing Database...")
        init_database(db_engine)

    try:
        quote_requests_sample = pd.read_csv("quote_requests_sample.csv")
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        print(f"FATAL: Error loading test data: {e}")
        return

    # Get initial state
    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    print("[SETUP] Creating agents...")
    # inventory_checker_agent = InventoryCheckerAgent(model, verbosity_level=SMOLAGENT_VERBOSITY)
    inventory_manager_agent = InventoryManagerAgent(
        model, verbosity_level=SMOLAGENT_VERBOSITY
    )
    quote_agent = QuoteAgent(model, verbosity_level=SMOLAGENT_VERBOSITY)
    customer_agent = CustomerAgent(model, verbosity_level=SMOLAGENT_VERBOSITY)
    fulfillment_agent = FulfillmentAgent(model, verbosity_level=SMOLAGENT_VERBOSITY)
    orchestrator = OrchestratorAgent(
        model,
        inventory_manager_agent,
        quote_agent,
        customer_agent,
        fulfillment_agent,
        verbosity_level=SMOLAGENT_VERBOSITY,
    )
    print("All agents created successfully\n")

    results = [] 
    fulfilled_count = 0
    unfulfilled_count = 0

    # count = 0
    # for request_num, (idx, row) in enumerate(quote_requests_sample.iterrows(), 1):
    # MANUAL DEBUG: Set request_num here to debug a specific request
    request_num = 0
    row = quote_requests_sample.loc[request_num]
    request_date = row["request_date"].strftime("%Y-%m-%d")

    print(f"\n=== Request {request_num} ===")
    print(f"Context: {row['job']} organizing {row['event']}")
    print(f"Request Date: {request_date}")
    print(f"Cash Balance: ${current_cash:.2f}")
    print(f"Inventory Value: ${current_inventory:.2f}")

    # Process request
    request_with_date = f"{row['request']} (Date of request: {request_date})"

    response, fulfilled, fulfillment_details = (
        orchestrator.process_customer_request(request_with_date, request_date)
    )

    if fulfilled:
        fulfilled_count += 1
    else:
        unfulfilled_count += 1

    # Update state
    report = generate_financial_report(request_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    print(f"Fulfilled: {fulfilled}")
    print(f"Details: {fulfillment_details}")
    print(f"Updated Cash: ${current_cash:.2f}")
    print(f"Updated Inventory: ${current_inventory:.2f}")

    results.append(
        {
            "request_id": request_num,
            "request_date": request_date,
            "cash_balance": current_cash,
            "inventory_value": current_inventory,
            "fulfilled": fulfilled,
            "fulfillment_details": fulfillment_details,
            "response": response,
        }
    )

    # time.sleep(1)
        # count += 1
        # if count % 5 == 0:
            # break
        # break

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")
    print("\nFulfillment Summary:")
    print(f"Total Requests: {len(results)}")
    print(f"Fulfilled: {fulfilled_count}")
    print(f"Unfulfilled: {unfulfilled_count}")

    # Show requests with cash balance changes
    print("\n===== REQUESTS WITH CASH BALANCE CHANGES =====")
    initial_cash = 50000.0
    for result in results:
        if result["cash_balance"] != initial_cash:
            print(
                f"Request {result['request_id']}: ${initial_cash:.2f} -> ${result['cash_balance']:.2f} | Fulfilled: {result['fulfilled']}"
            )

    # Save results - append to existing CSV if it exists
    results_df = pd.DataFrame(results)
    if os.path.exists("test_results.csv"):
        existing_df = pd.read_csv("test_results.csv")
        results_df = pd.concat([existing_df, results_df], ignore_index=True)
    results_df.to_csv("test_results.csv", index=False)
    return results


if __name__ == "__main__":
    # Uncomment the line below to run the full test scenarios instead
    _ = run_test_scenarios()
