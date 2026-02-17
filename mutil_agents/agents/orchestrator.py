from smolagents import CodeAgent, OpenAIServerModel
from typing import List

import os
import dotenv

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
            sub_agents: A list of instantiated agent objects (e.g. [InventoryManager(), SalesAgent()]).
            **kwargs: Additional arguments for the base CodeAgent.
        """

        # 2. Define the System Prompt
        # We dynamically list the team members in the prompt so the LLM knows who to call.
        team_descriptions = "\n".join(
            [f"- {a.name}: {a.description}" for a in managed_team]
        )

        # 3. UPDATED System Prompt
        # Added Rule #5 specifically for closing sales.
        system_prompt = f"""
        You are the Autonomous Order Processing System for Beaver's Choice Paper Company.
        Current Simulation Date: {get_simulation_date_str()}
        
        Your Goal: Process incoming customer requests automatically. 
        You must decide whether to FULFILL or REJECT the order based on feasibility.
        There is NO human user to ask for confirmation. You must decide.
        
        Your Team:
        {team_descriptions}
        
        --- EXECUTION LOGIC (Follow this Step-by-Step) ---
        
        STEP 1: ANALYZE & CHECK FEASIBILITY
        - Extract the Item Name, Quantity, and Deadline from the request.
        - Call 'inventory_manager' to check 'validate_delivery'.
        - Call 'quoting_specialist' to check 'calculate_quote' (to get the price).
        
        STEP 2: MAKE THE DECISION
        - **IF delivery is IMPOSSIBLE** (Deadline passed or supplier too slow):
            -> REJECT the order. State the reason clearly. STOP.
            
        - **IF delivery is FEASIBLE** (Stock exists OR Restock can arrive in time):
            -> PROCEED to Step 3.
            
        STEP 3: EXECUTE (The "Action" Phase)
        - **IF Restock Needed**: Instruct 'inventory_manager' to 'restock_item' immediately to cover the shortage.
        - **FINALIZE SALE**: Instruct 'sales_finance_manager' to 'finalize_sale' using the price calculated in Step 1.
        
        STEP 4: REPORT
        - Output a final summary: "Order Processed: [Yes/No]. Transaction ID: [ID]. Total Price: [$X]. Delivery Estimate: [Date]."
        
        --- RULES ---
        1. **Do not ask questions.** The user is not here. You act on the request text alone.
        2. **If stock is low but restock is fast enough**: You MUST order the restock AND process the sale. This is "Just-In-Time" fulfillment.
        3. **Failure is acceptable**: If you cannot meet the deadline, it is better to say "Rejected" than to lie.
        """

        # 3. Initialize the Parent Class
        super().__init__(
            tools=[],  # Orchestrator has no direct tools, only sub-agents
            managed_agents=managed_team,
            model=model,
            name="orchestrator",
            description="The main interface for handling customer requests and delegating tasks.",
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

    res = orchestrator.run(
        """I would like to order 100 of 'A4 paper' by April 15, 2025"""
    )

    print(res)
