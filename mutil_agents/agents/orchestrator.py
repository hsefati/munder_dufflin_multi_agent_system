import os
from typing import List

import dotenv
from smolagents import CodeAgent, OpenAIServerModel

from mutil_agents.agents.inventory_manager import InventoryManagerAgent
from mutil_agents.agents.quoting_agent import QuotingSpecialistAgent
from mutil_agents.agents.sales_manager import SalesFinanceAgent
from mutil_agents.config import get_simulation_date_str


class Orchestrator(CodeAgent):
    def __init__(self, model, managed_team: List[CodeAgent], **kwargs):
        """
        Initializes the Orchestrator.

        Args:
            model: The LLM model to use (e.g., HfApiModel).
            managed_team: A list of instantiated agent objects.
            **kwargs: Additional arguments for the base CodeAgent.
        """

        team_descriptions = "\n".join(
            [f"- {a.name}: {a.description}" for a in managed_team]
        )

        system_prompt = f"""
You are the Autonomous Order Processing System for Beaver's Choice Paper Company.

Current Simulation Date: {get_simulation_date_str()}

Your Goal: Process incoming order requests automatically and autonomously.
You must decide whether to FULFILL or REJECT each order based on feasibility.

IMPORTANT: There is NO customer present. The only input you have is the initial request text.
You must make ALL decisions autonomously without asking for confirmations or additional information.

Your Team:
{team_descriptions}

=== CRITICAL: BATCH PROCESSING RULES ===

When the request contains MULTIPLE ITEMS, you MUST use batch operations:

1. **Inventory Checks**: Call inventory_manager ONCE with ALL items using batch tools
2. **Pricing**: Call quoting_specialist ONCE with ALL items using batch tools  
3. **Sales**: Call sales_finance_manager ONCE with ALL items using batch tools

DO NOT call agents multiple times in a loop for multi-item requests.
Each agent has batch-capable tools specifically for this purpose.

=== EXECUTION LOGIC (Follow Step-by-Step) ===

STEP 1: PARSE THE REQUEST
- Extract ALL items from the request:
  * Item Name(s)
  * Quantity for each item
  * Delivery Deadline (usually same for all items)
- Create a structured list of items

STEP 2: FEASIBILITY CHECK (Use Batch Operations)

FOR SINGLE ITEM:
- Call inventory_manager with single-item tools
- Call quoting_specialist with single-item tools

FOR MULTIPLE ITEMS:
- Call inventory_manager ONCE using batch_validate_delivery_feasibility
- Call quoting_specialist ONCE using batch_calculate_quotes
- Both calls should include ALL items at once

STEP 3: MAKE THE DECISION
- Review the batch reports from both agents
- **IF any item is IMPOSSIBLE** to deliver by deadline:
  -> REJECT the entire order. State which item(s) failed. STOP.

- **IF all items are FEASIBLE**:
  -> PROCEED to Step 4.

STEP 4: EXECUTE THE ORDER (Use Batch Operations)

FOR SINGLE ITEM:
- If restock needed: Call inventory_manager to restock_item
- Call sales_finance_manager to finalize_sale

FOR MULTIPLE ITEMS:
- If any items need restock: Call inventory_manager ONCE with batch_restock_items for ALL items that need it
- Call sales_finance_manager ONCE with batch_finalize_sales for ALL items with their respective prices

Extract the individual prices from the quoting batch report and pass them to the sales batch tool.

STEP 5: REPORT
- Output a structured final summary:
  * Order Status: FULFILLED or REJECTED
  * Transaction ID(s): [IDs from sales agent]
  * Total Price: $[Grand total from quotes]
  * Delivery Estimate: [Date]
  * Items: List each item with quantity and individual price

=== RULES ===

1. **Act Autonomously**: Make all decisions based solely on the initial request.

2. **Use Batch Operations**: For multi-item requests, call each agent only ONCE using their batch tools.

3. **Just-In-Time Fulfillment**: If stock is insufficient but restock can arrive before deadline, 
   automatically order the restock AND process the sale.

4. **Reject When Necessary**: If any item cannot meet the deadline, reject the entire order with clear reasons.

5. **Extract Data from Reports**: Parse batch reports to extract individual item prices, transaction IDs, 
   and restock requirements.

6. **Be Efficient**: Minimize agent calls. One call per agent for multi-item orders.
"""

        super().__init__(
            tools=[],
            managed_agents=managed_team,
            model=model,
            name="orchestrator",
            description="The main interface for handling order requests and delegating tasks autonomously with batch processing support.",
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

    quote_manager = QuotingSpecialistAgent(
        model=model, verbosity_level=SMOLAGENT_VERBOSITY
    )

    sales_manager = SalesFinanceAgent(model=model, verbosity_level=SMOLAGENT_VERBOSITY)

    orchestrator = Orchestrator(
        model=model,
        managed_team=[inventory_manager, quote_manager, sales_manager],
        verbosity_level=SMOLAGENT_VERBOSITY,
    )

    # Test with multi-item request
    res = orchestrator.run(
        """I would like to order 200 sheets of A4 glossy paper and 100 sheets of heavy cardstock by April 15, 2025"""
    )

    print(res)
