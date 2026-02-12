"""Orchestrator Agent - coordinates all agents and manages customer interactions."""

import json
import re
from datetime import datetime
from typing import Dict, Tuple
from smolagents import ToolCallingAgent, OpenAIServerModel, CodeAgent

# from mutil_agents.agents.inventory_agent import InventoryStatus
# from mutil_agents.agents.inventory_management import InventoryManagerStatus
from mutil_agents.agents.inventory_management_v2 import InventoryManagerStatus
from mutil_agents.agents.quote_agent import QuoteDetails
from mutil_agents.agents.customer_agent import CustomerDecision
from mutil_agents.agents.fulfillment_agent import FulfillmentReceipt


class OrchestratorAgent(CodeAgent):
    """Agent responsible for coordinating all other agents and managing customer interactions."""

    def __init__(
        self,
        model: OpenAIServerModel,
        # inventory_checker_agent,
        inventory_manager_agent,
        quote_agent,
        customer_agent,
        fulfillment_agent,
        verbosity_level: int = 0,
    ):
        # self.inventory_checker_agent = inventory_checker_agent
        self.inventory_manager_agent = inventory_manager_agent
        self.quote_agent = quote_agent
        self.customer_agent = customer_agent
        self.fulfillment_agent = fulfillment_agent

        super().__init__(
            name="OrchestratorAgent",
            model=model,
            tools=[],
            verbosity_level=verbosity_level,
            description="""Master orchestrator agent that manages the entire order processing workflow.
            You coordinate between InventoryCheckerAgent, InventoryManagerAgent, QuoteAgent, CustomerAgent, and FulfillmentAgent to handle customer requests.
            
            Your workflow:
            1. INVENTORY CHECKER: Use InventoryCheckerAgent to:
               - Check current stock levels for requested items
               
            2. INVENTORY MANAGER: Use InventoryManagerAgent to:
               - Analyze inventory status and identify low stock situations
               - Check reorder requirements
               - Estimate supplier delivery timelines if restocking is needed
            
            3. QUOTE GENERATION: Use QuoteAgent to:
               - Generate pricing quotes based on inventory availability
               - Apply appropriate bulk discounts
               - Provide itemized breakdown
            
            4. CUSTOMER APPROVAL: Present quote and delivery timeline to customer
               - Show final price
               - Show estimated delivery date
               - Request customer approval and payment confirmation
            
            5. ORDER FULFILLMENT: Use FulfillmentAgent to:
               - Execute order after customer approval
               - Record sales transaction
               - Generate order confirmation
               - Provide tracking details
            
            Your responsibilities:
            - Manage the complete order lifecycle
            - Coordinate information flow between agents
            - Handle customer communications
            - Make decisions based on business logic
            - Provide final order confirmation and receipt
            
            Always follow the workflow in order: Check Inventory → Analyze Stock → Generate Quote → Get Approval → Fulfill Order.""",
        )

    def _extract_json_from_response(self, response: str) -> Dict:
        """
        Extract JSON object from agent response text.

        Args:
            response (str): Raw response from agent which may contain JSON

        Returns:
            Dict: Extracted JSON object or empty dict if not found
        """
        try:
            # Try to find JSON in the response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
        except (json.JSONDecodeError, AttributeError):
            pass
        return {}

    # def _parse_inventory_response(self, response: dict) -> InventoryStatus:
    #     """Parse inventory checker agent response into InventoryStatus object."""
    #     try:
    #         if response:
    #             return InventoryStatus(**response)
    #     except Exception as e:
    #         print(f"Warning: Could not parse inventory response: {e}")
    #     return InventoryStatus(available_items={}, missing_items=[])

    def _parse_inventory_manager_response(
        self, response: dict
    ) -> InventoryManagerStatus:
        """Parse inventory manager agent response into InventoryManagerStatus object."""
        try:
            if response:
                return InventoryManagerStatus(**response)
        except Exception as e:
            print(f"Warning: Could not parse inventory manager response: {e}")
        return InventoryManagerStatus(
            available_items={},
            missing_items=[],
            low_stock=[],
            reorder_required=False,
            delivery_timelines={},
        )

    def _parse_quote_response(self, response: dict) -> QuoteDetails:
        """Parse quote agent response into QuoteDetails object."""
        try:
            if response:
                return QuoteDetails(**response)
        except Exception as e:
            print(f"Warning: Could not parse quote response: {e}")
        return QuoteDetails(
            total_price=0.0, quoted_items={}, unavailable_items=[], bulk_discount="0%"
        )

    def _parse_customer_decision(self, response: dict) -> CustomerDecision:
        """Parse customer agent response into CustomerDecision object."""
        try:
            # First try structured JSON format
            if response:
                return CustomerDecision(**response)
        except Exception as e:
            print(f"Warning: Could not parse customer decision: {e}")
        return CustomerDecision(decision="DECLINE", reason="Unable to parse decision")

    def _parse_fulfillment_response(self, response: str) -> FulfillmentReceipt:
        """Parse fulfillment agent response into FulfillmentReceipt object."""
        try:
            data = self._extract_json_from_response(response)
            if data:
                return FulfillmentReceipt(**data)
        except Exception as e:
            print(f"Warning: Could not parse fulfillment response: {e}")
        return FulfillmentReceipt(
            status="pending", transaction_id="N/A", delivery_date="TBD"
        )

    def process_customer_request(
        self, customer_request: str, request_date: str = ""
    ) -> Tuple[str, bool, str]:
        """
        Execute the complete order processing workflow for a customer request.
        Handles structured outputs from agents using BaseModel classes.

        Args:
            customer_request (str): Natural language customer inquiry or order request
            request_date (str): ISO format date for the request

        Returns:
            tuple: (final_response, fulfilled, fulfillment_details)
        """
        if not request_date:
            request_date = datetime.now().strftime("%Y-%m-%d")

        print("\n" + "=" * 80)
        print("ORCHESTRATOR: Processing customer request...")
        print("=" * 80)

        fulfilled = False
        fulfillment_details = ""

        try:
            # STEP 1A: Inventory Check (InventoryCheckerAgent)
            print("\n[STEP 1A] Checking current inventory levels...")
            checker_response = self.inventory_manager_agent.run(customer_request)
            print(f"\n[Inventory Checker Agent Response]:\n{checker_response}\n")
            inventory_data = self._parse_inventory_manager_response(checker_response)
            print(f"[Parsed Inventory Data]: {inventory_data}\n")

            # # STEP 1B: Inventory Management (InventoryManagerAgent)
            # print("[STEP 1B] Analyzing inventory status and reorder requirements...")
            # # manager_context = f"Customer request: {customer_request}\nCurrent Inventory: {inventory_data.dict()}"
            # manager_response = self.inventory_manager_agent.run(
            # "Please process the inventory report for the provided customer request.",
            # additional_args={
            #     "current_inventory": inventory_data.model_dump()  # Convert Pydantic model to dict for agent input
            # })

            # print(f"\n[Inventory Manager Agent Response]:\n{manager_response}\n")
            # inventory_manager_data = self._parse_inventory_manager_response(manager_response)
            # print(f"[Parsed Inventory Manager Data]: {inventory_manager_data}\n")

            # STEP 2: Generate Quote
            print("[STEP 2] Generating pricing quote...")
            # quote_context = f"Customer request: {customer_request}\nInventory Status: {inventory_manager_data.dict()}"
            # quote_response = self.quote_agent.run(quote_context)
            quote_response = self.quote_agent.run(
                "Based on the inventory_data, generate a quote for the missing_items. "
                "Assume we need to order 200 units of each to meet minimum stock levels.",
                additional_args={"inventory_info": inventory_data},
            )
            print(f"\n[Quote Agent Response]:\n{quote_response}\n")
            quote_data = self._parse_quote_response(quote_response)
            print(f"[Parsed Quote Data]: {quote_data}\n")

            # STEP 3: Customer Decision
            print("[STEP 3] Customer Review and Decision...")
            # customer_context = f"Review this quote and decide:\nTotal Price: ${quote_data.total_price}\nItems: {quote_data.quoted_items}\nDiscount: {quote_data.bulk_discount}"
            # customer_response = self.customer_agent.run(customer_context)
            customer_response = self.customer_agent.run(
                """
    Review the 'quote_summary' and 'original_request'. 
    
    1. Check if the 'quoted_items' match what the customer wanted.
    2. Evaluate if the 'bulk_discount' makes the deal attractive.
    3. IMPORTANT: Check 'unavailable_items'. If critical items are missing, 
       consider if the delivery delay is acceptable.
    
    Provide a final decision (Approve/Decline) and a brief justification 
    mentioning the total price and the impact of discounts.
    """,
                additional_args={
                    "quote_summary": {
                        "total": quote_data.total_price,
                        "items": quote_data.quoted_items,
                        "discount_applied": quote_data.bulk_discount,
                        "out_of_stock": quote_data.unavailable_items,
                    },
                    "original_request": customer_request,
                },
            )
            print(f"\n[Customer Agent Response]:\n{customer_response}\n")
            customer_decision = self._parse_customer_decision(customer_response)
            print(f"[Parsed Customer Decision]: {customer_decision}\n")

            # STEP 4: Order Fulfillment - Only if approved
            if customer_decision.decision.upper() == "APPROVE":
                print("[STEP 4] Executing order fulfillment...")
                fulfillment_response = self.fulfillment_agent.run(
    """
    The customer has made a decision. 
    If approved, please process the fulfillment for all items in the quote.
    Use today's date (2025-04-01) for the transaction_date.
    """,
    additional_args={
        "quote_data": quote_data,
        "decision": customer_decision # This contains "APPROVE" or "DECLINE"
    }
)
            else:
                print("[STEP 4] Order Declined - No fulfillment")
                fulfillment_response = f"Customer declined: {customer_decision.reason}"

            print(f"\n[Fulfillment Agent Response]:\n{fulfillment_response}\n")
            fulfillment_data = self._parse_fulfillment_response(fulfillment_response)
            print(f"[Parsed Fulfillment Data]: {fulfillment_data}\n")

            # Determine if order was fulfilled
            if fulfillment_data.status.lower() == "success":
                fulfilled = True
                fulfillment_details = f"Order fulfilled with Transaction ID: {fulfillment_data.transaction_id}, Delivery: {fulfillment_data.delivery_date}"
            else:
                fulfilled = (
                    customer_decision.decision.upper() == "APPROVE"
                    and fulfillment_data.status.lower() != "pending"
                )
                fulfillment_details = f"Status: {fulfillment_data.status}, Transaction: {fulfillment_data.transaction_id}"

            # FINAL RESPONSE - Structured Summary
            final_response = f"""
================================================================================
                         ORDER PROCESSING COMPLETE
                            FINAL SUMMARY
================================================================================

STEP 1A - INVENTORY CHECK
  Available Items: {inventory_data.available_items}
  Missing Items: {inventory_data.missing_items}
    Low Stock Items: {inventory_data.low_stock}
    Reorder Required: {inventory_data.reorder_required}
    Delivery Timelines: {inventory_data.delivery_timelines}

STEP 2 - PRICING QUOTE
  Total Price: ${quote_data.total_price:.2f}
  Bulk Discount: {quote_data.bulk_discount}
  Quoted Items: {json.dumps(quote_data.quoted_items, indent=2)}
  Unavailable Items: {quote_data.unavailable_items}

STEP 3 - CUSTOMER DECISION
  Decision: {customer_decision.decision}
  Reason: {customer_decision.reason}

STEP 4 - ORDER FULFILLMENT
  Status: {fulfillment_data.status}
  Transaction ID: {fulfillment_data.transaction_id}
  Delivery Date: {fulfillment_data.delivery_date}

================================================================================
                       END OF ORDER PROCESSING
================================================================================
"""
            print(final_response)
            return final_response, fulfilled, fulfillment_details

        except Exception as e:
            error_message = f"ERROR in order processing: {str(e)}"
            print(f"\nERROR: {error_message}")
            return error_message, False, str(e)
