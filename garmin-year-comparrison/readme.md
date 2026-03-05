# Garmin Year-over-Year Comparison 

A Python script designed to visually and statistically compare your Garmin activity data between two different years.
  
While reviewing a single year is great, tracking long-term progress requires context. I wanted a way to directly compare how my training habits, total volume, and specific disciplines (like cycling or basketball) have shifted from one year to the next side-by-side, which is not easily done within the Garmin Connect app.
  
   
This script provides a direct, head-to-head comparison:
1. **Multi-Year Fetching:** Downloads and caches activity data for two explicitly defined years (e.g., 2024 vs. 2025).
2. **Comparative Visuals:** Generates charts that map the years over each other:
   - Cumulative training hours over the 365 days.
   - Grouped monthly volume comparisons.
   - 100% stacked bar charts showing how your discipline focus shifted.
   - Progression scatter plots (e.g., Distance vs. Elevation for Cycling).
3. **YoY Metric Deltas:** Calculates percentage increases/decreases (deltas) for core metrics like distance, activities, and active calories.
4. **Markdown Export:** Outputs a structured `comparison_YYYY_vs_YYYY.md` file with tables and charts automatically embedded.

## How to use it

### 1. Prerequisites
* Python 3
* A valid Garmin Connect account.
* A `garmin_config.json` file in the project directory structured as:
  ```json
  {
      "email": "your_email@example.com",
      "password": "your_password"
  }
  ```

### 2. Setup
Create a virtual environment and install the dependencies (if not done globally):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install garminconnect pandas numpy matplotlib seaborn
```

### 3. Run
Execute the script by providing the two years you want to compare:
```bash
python compare_years.py 2024 2025
```
The output, including the comparison images and Markdown report, will be strictly organized within the `out/YYYY_vs_YYYY/` directory.
