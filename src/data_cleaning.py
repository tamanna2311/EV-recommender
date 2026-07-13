import pandas as pd
import numpy as np
import re
import os

def clean_price(price_str):
    if pd.isna(price_str):
        return np.nan
    # Extract numerical value from something like "Rs. 19.49 Lakh"
    match = re.search(r'(\d+\.?\d*)', str(price_str))
    if match:
        return float(match.group(1))
    return np.nan

def clean_numeric(val_str):
    if pd.isna(val_str) or str(val_str).lower() == 'none':
        return np.nan
    # Extract first sequence of digits/decimals
    match = re.search(r'(\d+\.?\d*)', str(val_str))
    if match:
        return float(match.group(1))
    return np.nan

def clean_boolean(val_str):
    if pd.isna(val_str):
        return False
    if str(val_str).lower().strip() in ['yes', 'y', 'true', '1']:
        return True
    return False

def clean_data():
    raw_path = 'data/raw_ev_data.csv'
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"{raw_path} not found. Run data_collection.py first.")
        
    df = pd.read_csv(raw_path)

    required_defaults = {
        'price_ex_showroom_lakh': np.nan,
        'price_on_road_lakh': np.nan,
        'min_price_lakh': np.nan,
        'max_price_lakh': np.nan,
        'battery_capacity_kwh': np.nan,
        'claimed_range_km': np.nan,
        'real_world_range_km': np.nan,
        'charging_time_ac_hours': np.nan,
        'charging_time_dc_minutes': np.nan,
        'fast_charging_available': False,
        'motor_power_kw': np.nan,
        'torque_nm': np.nan,
        'top_speed_kmph': np.nan,
        'acceleration_0_100_sec': np.nan,
        'body_type': 'SUV',
        'segment': 'SUV',
        'seating_capacity': 5,
        'boot_space_litres': np.nan,
        'ground_clearance_mm': np.nan,
        'safety_rating': np.nan,
        'airbags': np.nan,
        'home_charging_supported': True,
        'sales_latest_month': 0,
        'sales_previous_month': 0,
        'sales_3_months_ago': 0,
        'variants_count': 1,
    }
    for column, default in required_defaults.items():
        if column not in df.columns:
            df[column] = default
    
    # 1. Clean Prices (Lakh)
    df['price_ex_showroom_lakh'] = df['price_ex_showroom_lakh'].apply(clean_price)
    df['price_on_road_lakh'] = df['price_on_road_lakh'].apply(clean_price)
    df['min_price_lakh'] = df['min_price_lakh'].apply(clean_price)
    df['max_price_lakh'] = df['max_price_lakh'].apply(clean_price)
    
    # 2. Clean numeric strings with units
    numeric_cols = [
        'battery_capacity_kwh',
        'claimed_range_km',
        'real_world_range_km',
        'charging_time_ac_hours',
        'charging_time_dc_minutes',
        'motor_power_kw',
        'torque_nm',
        'top_speed_kmph',
        'acceleration_0_100_sec',
        'seating_capacity',
        'boot_space_litres',
        'ground_clearance_mm',
        'safety_rating',
        'airbags',
        'warranty_years',
        'battery_warranty_years',
        'battery_warranty_km'
    ]
    
    optional_numeric_cols = [
        'variants_count',
        'sales_latest_month',
        'sales_previous_month',
        'sales_3_months_ago',
        'user_rating',
        'rating_count',
    ]

    for col in numeric_cols + optional_numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)
        
    # 3. Clean boolean columns
    bool_cols = ['fast_charging_available', 'home_charging_supported']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_boolean)
        
    # 4. Handle Missing Values
    # Assume 0 boot space if missing, average charging time if missing, etc.
    df['boot_space_litres'] = df['boot_space_litres'].fillna(0)
    df['safety_rating'] = df['safety_rating'].fillna(3.0).clip(0, 5)
    df['seating_capacity'] = df['seating_capacity'].fillna(5)
    df['claimed_range_km'] = df['claimed_range_km'].fillna(df['claimed_range_km'].median())
    df['real_world_range_km'] = df['real_world_range_km'].fillna(df['claimed_range_km'] * 0.78)
    df['battery_capacity_kwh'] = df['battery_capacity_kwh'].fillna(df['battery_capacity_kwh'].median())
    df['motor_power_kw'] = df['motor_power_kw'].fillna(df['motor_power_kw'].median())
    df['acceleration_0_100_sec'] = df['acceleration_0_100_sec'].fillna(15)
    
    # For DC charging time, if missing, we can estimate or put a high value (like 120 mins) 
    # to penalize it in feature engineering, but we'll leave as NaN and handle in feature engineering
    # or fill with median.
    dc_median = df['charging_time_dc_minutes'].median()
    if np.isnan(dc_median):
        dc_median = 120
    df['charging_time_dc_minutes'] = df['charging_time_dc_minutes'].fillna(dc_median)
    
    # Calculate some rough suitability scores out of 10 for the requirements
    # (These will be further refined in feature_engineering, but good to have base scores)
    
    output_path = 'data/ev_cars_cleaned.csv'
    df.to_csv(output_path, index=False)
    print(f"Cleaned data successfully saved to {output_path}")
    
    generate_data_dictionary()

def generate_data_dictionary():
    dict_content = """# Data Dictionary: EV Cars

| Column Name | Data Type | Description |
|-------------|-----------|-------------|
| car_id | String | Unique identifier for the car |
| car_name | String | Full name of the car (Brand + Model) |
| brand | String | Manufacturer brand name |
| model | String | Model name |
| variant | String | Specific variant/trim of the model |
| price_ex_showroom_lakh | Float | Ex-showroom price in Lakhs |
| price_on_road_lakh | Float | Estimated on-road price in Lakhs |
| min_price_lakh | Float | Minimum starting price for the model range |
| max_price_lakh | Float | Maximum top-end price for the model range |
| battery_capacity_kwh | Float | Battery capacity in Kilowatt-hours (kWh) |
| claimed_range_km | Float | ARAI/WLTP claimed range in kilometers |
| real_world_range_km | Float | Estimated real-world range in kilometers |
| charging_time_ac_hours | Float | Normal AC charging time from 0-100% in hours |
| charging_time_dc_minutes | Float | Fast DC charging time from 10-80% in minutes |
| fast_charging_available | Boolean | Whether DC fast charging is supported |
| motor_power_kw | Float | Maximum power output of the electric motor in kW |
| torque_nm | Float | Maximum torque output in Nm |
| top_speed_kmph | Float | Top speed of the car in km/h |
| acceleration_0_100_sec | Float | Time taken to accelerate from 0 to 100 km/h in seconds |
| body_type | String | Car body type (e.g., SUV, Hatchback, Sedan) |
| segment | String | Market segment (e.g., Compact SUV, Premium) |
| seating_capacity | Float | Number of seats |
| boot_space_litres | Float | Luggage capacity in liters |
| ground_clearance_mm | Float | Ground clearance in millimeters |
| safety_rating | Float | Global NCAP safety rating (out of 5) |
| airbags | Float | Number of airbags provided |
| transmission | String | Type of transmission (usually Automatic for EVs) |
| drive_type | String | Drivetrain type (FWD, RWD, AWD) |
| warranty_years | Float | Standard vehicle warranty in years |
| battery_warranty_years | Float | Battery warranty in years |
| battery_warranty_km | Float | Battery warranty in kilometers |
| home_charging_supported | Boolean | Whether a home charger is provided/supported |
| pros | String | Advantages and highlights of the car |
| cons | String | Disadvantages and drawbacks of the car |
| source_url | String | URL of the data source |
| last_updated | String | Date of last data update |
| status | String | Market availability status |
| price_text | String | Human-readable source price range |
| range_text | String | Human-readable source range |
| battery_text | String | Human-readable source battery range |
| charging_text | String | Charging text from source data |
| useful_features | String | Extracted feature highlights from source data |
| variants_count | Float | Number of variants listed by the source |
| image_url | String | Model image URL used by mobile cards |
| image_source_url | String | Source page for the image |
| data_source | String | Name of the source used for this row |
| data_collected_date | String | Date the source row was collected |
| sales_latest_month | Float | Latest model-wise monthly sales, when known |
| sales_previous_month | Float | Previous monthly sales, when known |
| sales_3_months_ago | Float | Sales from three months ago, when known |
| sales_data_month | String | Month represented by sales_latest_month |
| sales_source | String | Source note for the sales data |
"""
    with open('data/data_dictionary.md', 'w') as f:
        f.write(dict_content)
    print("Data dictionary saved to data/data_dictionary.md")

if __name__ == '__main__':
    clean_data()
