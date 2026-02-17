from datetime import datetime

# Set the simulation "Today" to match your dataset's timeframe
SIMULATION_DATE = datetime(2025, 4, 1)

def get_simulation_date() -> datetime:
    return SIMULATION_DATE

def get_simulation_date_str() -> str:
    return SIMULATION_DATE.strftime("%Y-%m-%d")