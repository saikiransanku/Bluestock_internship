import requests
import pandas as pd
import os

os.makedirs("data/raw", exist_ok=True)

funds = {
    "hdfc_top_100": 125497,
    "sbi_bluechip": 119551,
    "icici_bluechip": 120503,
    "nippon_large_cap": 118632,
    "axis_bluechip": 119092,
    "kotak_bluechip": 120841
}

def fetch_and_save_nav(fund_name, scheme_code):
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        nav_data = data['data']
        
        # Convert to DataFrame
        df = pd.DataFrame(nav_data)
        
        # Save CSV
        file_path = f"data/raw/{fund_name}_nav.csv"
        df.to_csv(file_path, index=False)
        
        print(f"Saved: {file_path}")
    else:
        print(f"Failed for {fund_name}")
for name, code in funds.items():
    fetch_and_save_nav(name, code)

print("All NAV data fetched successfully!")