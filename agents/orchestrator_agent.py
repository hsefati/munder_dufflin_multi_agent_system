"""Orchestrator Agent - coordinates all agents and manages customer interactions."""

import json
import re
from datetime import datetime
from typing import Dict, Tuple
from pydantic import BaseModel
from smolagents import ToolCallingAgent, OpenAIServerModel


class InventoryStatus(BaseModel):
    items: Dict[str, int]
    low_stock: list
    reorder_required: bool
    restock_date: str = None  # type: ignore


class QuoteDetails(BaseModel):
    total_price: float
    itemized_breakdown: list
    discount_applied: str


class CustomerDecision(BaseModel):
    decision: str  # "APPROVE" or "DECLINE"
    reason: str


class FulfillmentReceipt(BaseModel):
    status: str
    transaction_id: str
    delivery_date: str


class OrchestratorAgent(ToolCallingAgent):
    """Agent responsible for coordinating all other agents and managing customer interactions."""
    def __init__(
        self,
        model: OpenAIServerModel,
        inventory_agent,
        quote_agent,
        customer_agent,
        fulfillment_agent,
        verbosity_level: int = 0
    ):
        self.inventory_agent = inventory_agent
        self.quote_agent = quote_agent
        self.customer_agent = customer_agent
        self.fulfillment_agent = fulfillment_agent
        
        super().__init__(
            name="OrchestratorAgent",
            model=model,
            tools=[],
            verbosity_level=verbosity_level,
            description="""Master orchestrator agent that manages the entire order processing workflow.
            You coordinate between InventoryAgent, QuoteAgent, CustomerAgent, and FulfillmentAgent to handle customer requests.
            
            Your workflow:
            1. INVENTORY CHECK: Use InventoryAgent to:
               - Check availability of requested items
               - Identify any low stock situations
               - Get supplier delivery timelines if restocking is needed
            
            2. QUOTE GENERATION: Use QuoteAgent to:
               - Generate pricing quotes based on inventory availability
               - Apply appropriate bulk discounts
               - Provide itemized breakdown
            
            3. CUSTOMER APPROVAL: Present quote and delivery timeline to customer
               - Show final price
               - Show estimated delivery date
               - Request customer approval and payment confirmation
            
            4. ORDER FULFILLMENT: Use FulfillmentAgent to:
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
            
            Always follow the workflow in order: Check Inventory → Generate Quote → Get Approval → Fulfill Order.""",
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
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
        except (json.JSONDecodeError, AttributeError):
            pass
        return {}
    
    def _parse_inventory_response(self, response: str) -> InventoryStatus:
        """Parse inventory agent response into InventoryStatus object."""
        try:
            data = self._extract_json_from_response(response)
            if data:
                return InventoryStatus(**data)
        except Exception as e:
            print(f"Warning: Could not parse inventory response: {e}")
        return InventoryStatus(items={}, low_stock=[], reorder_required=False, restock_date="")  # type: ignore
    
    def _parse_quote_response(self, response: str) -> QuoteDetails:
        """Parse quote agent response into QuoteDetails object."""
        try:
            data = self._extract_json_from_response(response)
            if data:
                return QuoteDetails(**data)
        except Exception as e:
            print(f"Warning: Could not parse quote response: {e}")
        return QuoteDetails(total_price=0.0, itemized_breakdown=[], discount_applied="0%")
    
    def _parse_customer_decision(self, response: str) -> CustomerDecision:
        """Parse customer agent response into CustomerDecision object."""
        try:
            # First try structured JSON format
            data = self._extract_json_from_response(response)
            if data and "decision" in data:
                return CustomerDecision(**data)
            
            # Fall back to parsing "DECISION: APPROVE/DECLINE" format
            if "DECISION: APPROVE" in response.upper():
                reason = response.split('\n')[1] if '\n' in response else "Approved"
                return CustomerDecision(decision="APPROVE", reason=reason)
            elif "DECISION: DECLINE" in response.upper():
                reason = response.split('\n')[1] if '\n' in response else "Declined"
                return CustomerDecision(decision="DECLINE", reason=reason)
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
        return FulfillmentReceipt(status="pending", transaction_id="N/A", delivery_date="TBD")

    def process_customer_request(self, customer_request: str, request_date: str = "") -> Tuple[str, bool, str]:
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
        
        print("\n" + "="*80)
        print("ORCHESTRATOR: Processing customer request...")
        print("="*80)
        
        fulfilled = False
        fulfillment_details = ""
        
        try:
            # STEP 1: Inventory Check
            print("\n[STEP 1] Checking inventory and stock status...")
            inventory_response = self.inventory_agent.run(customer_request)
            print(f"\n[Inventory Agent Response]:\n{inventory_response}\n")
            inventory_data = self._parse_inventory_response(inventory_response)
            print(f"[Parsed Inventory Data]: {inventory_data}\n")
                        
            # STEP 2: Generate Quote
            print("[STEP 2] Generating pricing quote...")
            quote_context = f"Customer request: {customer_request}\nInventory Status: {inventory_data.dict()}"
            quote_response = self.quote_agent.run(quote_context)
            print(f"\n[Quote Agent Response]:\n{quote_response}\n")
            quote_data = self._parse_quote_response(quote_response)
            print(f"[Parsed Quote Data]: {quote_data}\n")
            
            # STEP 3: Customer Decision
            print("[STEP 3] Customer Review and Decision...")
            customer_context = f"Review this quote and decide:\nTotal Price: ${quote_data.total_price}\nItems: {quote_data.itemized_breakdown}\nDiscount: {quote_data.discount_applied}"
            customer_response = self.customer_agent.run(customer_context)
            print(f"\n[Customer Agent Response]:\n{customer_response}\n")
            customer_decision = self._parse_customer_decision(customer_response)
            print(f"[Parsed Customer Decision]: {customer_decision}\n")
            
            # STEP 4: Order Fulfillment - Only if approved
            if customer_decision.decision.upper() == "APPROVE":
                print("[STEP 4] Executing order fulfillment...")
                fulfillment_context = f"""Customer approved the order.
                
Request: {customer_request}
Quote Details: Total ${quote_data.total_price}, Items: {json.dumps(quote_data.itemized_breakdown)}
Request Date: {request_date}
Delivery Date: {inventory_data.restock_date or request_date}"""
                fulfillment_response = self.fulfillment_agent.run(fulfillment_context)
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
                fulfilled = customer_decision.decision.upper() == "APPROVE" and fulfillment_data.status.lower() != "pending"
                fulfillment_details = f"Status: {fulfillment_data.status}, Transaction: {fulfillment_data.transaction_id}"
            
            # FINAL RESPONSE - Structured Summary
            final_response = f"""
================================================================================
                         ORDER PROCESSING COMPLETE
                            FINAL SUMMARY
================================================================================

STEP 1 - INVENTORY STATUS
  Available Items: {inventory_data.items}
  Low Stock Items: {inventory_data.low_stock}
  Reorder Required: {inventory_data.reorder_required}
  Restock Date: {inventory_data.restock_date}

STEP 2 - PRICING QUOTE
  Total Price: ${quote_data.total_price:.2f}
  Discount Applied: {quote_data.discount_applied}
  Itemized Breakdown: {json.dumps(quote_data.itemized_breakdown, indent=2)}

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
