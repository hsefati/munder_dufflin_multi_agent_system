```mermaid
graph TD
    %% Entry Point
    User[Customer Request] --> Orch

    subgraph MAS [Multi-Agent System]
        Orch[Orchestrator Agent]
        Inv[Inventory Agent]
        Quote[Quote Agent]
        Full[Fulfillment Agent]
    end

    %% Orchestration Flow
    Orch -->|1. Validate Stock| Inv
    Inv -->|Stock Data| Orch
    Orch -->|2. Request Pricing| Quote
    Quote -->|Price/Discount| Orch
    Orch -->|3. Execute Order| Full
    Full -->|Confirmation| Orch

    %% Tools Mapping
    subgraph Toolset [Tools and Helper Functions]
        T1[check_inventory_tool]
        T2[check_reorder_status_tool]
        T3[get_quote_history_tool]
        T4[create_order_fulfillment_tool]
        T5[check_delivery_timeline_tool]
    end

    %% Agent-Tool Interactions
    Inv --- T1
    Inv --- T2
    Quote --- T3
    Full --- T4
    Full --- T5
    Inv --- T5

    %% Database
    T1 & T2 & T3 & T4 --- DB[(Database)]

    %% Final Output
    Orch --> Result[Final Order Confirmation]
    ```