import logging
import os
import time

import dotenv
import pandas as pd
from smolagents import OpenAIServerModel
from sqlalchemy import create_engine

from mutil_agents.agents.inventory_manager import InventoryManagerAgent
from mutil_agents.agents.orchestrator import Orchestrator
from mutil_agents.agents.quoting_agent import QuotingSpecialistAgent
from mutil_agents.agents.sales_manager import SalesFinanceAgent
from mutil_agents.tools.tools import generate_financial_report, init_database

dotenv.load_dotenv()
OPENAI_API_KEY = os.getenv("UDACITY_OPENAI_API_KEY")
SMOLAGENT_VERBOSITY = int(os.getenv("SMOLAGENT_VERBOSITY", "1"))
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
    
    print("Initializing Database...")
    init_database(db_engine=db_engine)
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

    results = []
    count = 0
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")

        print(f"\n=== Request {idx+1} ===")
        print(f"Context: {row['job']} organizing {row['event']}")
        print(f"Request Date: {request_date}")
        print(f"Cash Balance: ${current_cash:.2f}")
        print(f"Inventory Value: ${current_inventory:.2f}")

        # Process request
        request_with_date = f"{row['request']} (Date of request: {request_date})"

        model = OpenAIServerModel(
        model_id="gpt-4o-mini",
        api_base="https://openai.vocareum.com/v1",
        api_key=OPENAI_API_KEY,
    )

        inventory_manager = InventoryManagerAgent(
            model=model, verbosity_level=SMOLAGENT_VERBOSITY
        )
        quote_manager = QuotingSpecialistAgent(
            model=model, verbosity_level=SMOLAGENT_VERBOSITY
        )
        sales_manager = SalesFinanceAgent(model=model, verbosity_level=SMOLAGENT_VERBOSITY)

        orchestrator = Orchestrator(
            model=model,
            managed_team=[inventory_manager, quote_manager, sales_manager],
            verbosity_level=SMOLAGENT_VERBOSITY,
            max_steps=30,
        )
        
        response = orchestrator.run(request_with_date)

        # Update state
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        print(f"Response: {response}")
        print(f"Updated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")

        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "cash_balance": current_cash,
                "inventory_value": current_inventory,
                "response": response,
            }
        )

        time.sleep(1)
        
        # if count >= 5:  # Limit to first 5 requests for testing
        #     break
        # count += 1

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")

    # Save results
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results


if __name__ == "__main__":
    # Uncomment the line below to run the full test scenarios instead
    _ = run_test_scenarios()
