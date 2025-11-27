import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE")
SERVICENOW_USERNAME = os.getenv("SERVICENOW_USERNAME")
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD")

def get_incidents():
    if not SERVICENOW_INSTANCE:
        raise ValueError("ServiceNow instance URL is missing!")
    
    url = f"{SERVICENOW_INSTANCE}/api/now/table/incident"
    params = {
        "sysparm_display_value": "true",
        "sysparm_limit": "20",
        "sysparm_fields": "number,short_description,priority,state,category,sys_created_on"
    }

    response = requests.get(url, auth=(SERVICENOW_USERNAME, SERVICENOW_PASSWORD), params=params)
    response.raise_for_status() 
    return response.json().get("result", [])
