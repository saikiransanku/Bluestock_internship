import pandas as pd
import os

data_path = "data/raw"
files = [f for f in os.listdir(data_path) if f.endswith(".csv")]

print("Files found:", files)

# 🔹 Loop for CSV exploration
for file in files:
    print("\n" + "="*50)
    print(f"Processing: {file}")
    
    df = pd.read_csv(os.path.join(data_path, file))

    print("Shape:", df.shape)
    print("Data Types:\n", df.dtypes)
    print("Head:\n", df.head())
    print("Missing Values:\n", df.isnull().sum())
    print("Duplicate Rows:", df.duplicated().sum())


# 🔹 AMFI VALIDATION (separate block)
# (ONLY run this if fund_master.csv exists)

"""
fund_master = pd.read_csv("data/raw/fund_master.csv")
nav_data = pd.read_csv("data/raw/hdfc_top_100_nav.csv")

fund_codes = set(fund_master['scheme_code'])
nav_codes = set(nav_data['scheme_code'])

missing = fund_codes - nav_codes

print("\nAMFI Validation")
print("Total fund_master codes:", len(fund_codes))
print("Total nav codes:", len(nav_codes))
print("Missing codes:", missing)
"""