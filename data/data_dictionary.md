# Data Dictionary: EV Cars

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
