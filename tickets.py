import json
from pathlib import Path

TICKET_FILE = Path(__file__).resolve().parent / "data" / "incident_data.json"

# Load tickets safely
def load_tickets():
    try:
        with open(TICKET_FILE, "r") as f:
            data = f.read().strip()
            if not data:
                return []
            return json.loads(data)
    except FileNotFoundError:
        save_tickets([])
        return []
    except json.JSONDecodeError:
        save_tickets([])
        return []

# Save tickets
def save_tickets(tickets):
    with open(TICKET_FILE, "w") as f:
        json.dump(tickets, f, indent=4)

# Add new ticket (if needed)
def add_ticket(ticket):
    tickets = load_tickets()
    tickets.append(ticket)
    save_tickets(tickets)
    return {"message": "Ticket added", "count": len(tickets)}
