# Beaver's Choice Paper Company: Multi-Agent System Report

## Executive Summary
This report documents the design, implementation, and evaluation of a multi-agent order processing system. The system successfully processed **20 customer quote requests**, fulfilling 10 orders (**50% fulfillment rate**) while appropriately rejecting 10 orders due to inventory or catalog constraints. The evaluation demonstrates the system's ability to autonomously manage inventory, calculate pricing with bulk discounts, execute financial transactions, and make intelligent decisions about order feasibility.

---

## 1. System Architecture and Agent Workflow

### 1.1 Architecture Overview: The "Hub and Spoke" Model
The system implements a **Central Orchestrator** pattern with three specialized agent roles, following a strict sequential workflow. This architecture ensures clear separation of concerns while maintaining coordinated decision-making.

**Design Philosophy:**
* **Separation of Concerns:** Each agent has a single, well-defined responsibility.
* **Sequential Execution:** Agents are called in a specific order to prevent redundant operations.
* **Autonomous Decision-Making:** The system operates without human intervention.
* **Database-Driven:** All pricing and inventory data comes from a live SQLite database.

### 1.2 Agent Roles and Responsibilities

| Agent | Role | Key Responsibilities |
| :--- | :--- | :--- |
| **Agent 1: Orchestrator** | Central Manager | Parses natural language, extracts entities, routes to specialists, and makes final FULFILL/REJECT decisions. |
| **Agent 2: Inventory Manager** | Logistics | Checks stock levels, validates delivery feasibility against deadlines, and executes restock orders. |
| **Agent 3: Quoting Specialist** | Finance/Pricing | Retrieves catalog prices, applies bulk discounts, and provides historical comparisons. |
| **Agent 4: Sales & Finance** | Accounting | Records finalized transactions, updates cash balances, and generates financial reports. |

#### **Discount Tiers Implemented:**
* **Standard (< 100 units):** 0% discount
* **Volume (100-999 units):** 10% discount
* **Bulk (1000+ units):** 20% discount

### 1.3 Workflow Logic
The system follows a strict 4-phase sequential workflow:

1.  **Phase 1: Feasibility Check**
    * *Orchestrator → Inventory Manager*
    * Decision Point: Can **ALL** items be delivered by the deadline? If NO, reject immediately.
2.  **Phase 2: Pricing Calculation**
    * *Orchestrator → Quoting Specialist*
    * Calculates individual item prices and the grand total.
3.  **Phase 3: Order Execution**
    * *Orchestrator → Inventory/Finance*
    * Triggers restocking (if needed) and finalizes the sale record in the database.
4.  **Phase 4: Reporting**
    * *Orchestrator*
    * Synthesizes a final response including transaction IDs and total costs.

---

## 2. Evaluation Results Analysis

### 2.1 Quantitative Results
| Metric | Value | Status |
| :--- | :--- | :--- |
| **Total Requests Processed** | 20 | Complete |
| **Successfully Fulfilled** | 10 (50%) | Met Requirement (≥ 3) |
| **Rejected Orders** | 10 (50%) | Validated constraints |
| **Initial Cash Balance** | $45,059.70 | - |
| **Final Cash Balance** | $21,409.70 | - |
| **Net Revenue Generated** | -$23,650.00 | Reflects restock costs |

### 2.2 Rejection Analysis
* **Items not in catalog (90%):** Detected before pricing/execution, saving token costs.
* **Deadline constraints (10%):** System correctly calculated supplier lead times (e.g., Request #3).

### 2.3 System Strengths
* **Batch Processing:** Specialist agents use batch-capable tools to handle multi-item orders (e.g., Request #5 with 6 items) in a single reasoning cycle.
* **Strict Modularity:** The Orchestrator has no DB access, ensuring that the system remains maintainable even if the database schema changes.
* **Just-in-Time Fulfillment:** The system automatically places restock orders when inventory is low but a deadline allows for replenishment.

---

## 3. Future Improvement Recommendations

### 3.1 Improvement #1: Fuzzy Name Matching
**Problem:** The system requires exact string matches (e.g., "A4 glossy paper" vs "Glossy Paper (A4)"), leading to high rejection rates for minor naming variations.
**Solution:** Integrate a similarity scoring algorithm (e.g., Levenshtein distance) within the Quoting Specialist agent.

### 3.2 Improvement #2: Partial Fulfillment Strategy
**Problem:** Currently, if one item in a multi-item order is unavailable, the entire order is rejected.
**Solution:** Implement logic to fulfill available items while flagging missing items for back-order or cancellation.

### 3.3 Improvement #3: Detailed Rejection Feedback
**Problem:** Rejection messages are often generic.
**Solution:** Enhance the Orchestrator's response synthesis to specify exactly which item name failed the catalog lookup to help the user correct their request.