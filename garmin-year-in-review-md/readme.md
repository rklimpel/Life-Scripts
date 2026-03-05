# Garmin Year in Review Generator 

A Python script that fetches your Garmin activity data for specified years and automatically generates a beautiful, data-rich Markdown report along with custom charts.

This script automates the creation of a deeply personalized annual review:
1. **Data Fetching:** Connects to the Garmin API and downloads all tracked activities for a given year (using local caching to avoid redundant API calls).
2. **Data Processing:** Uses `pandas` to aggregate data, calculating metrics like total hours, elevation, distance, and longest activity streaks.
3. **Custom Visualizations:** Generates tailored charts using `matplotlib` and `seaborn`:
   - Donut charts for discipline distribution.
   - Daily active calorie expenditure vs. resting metabolic trends.
   - Heatmaps revealing standard training times during the week.
   - Monthly progression stacked bar charts.
4. **Markdown Export:** Combines the statistics and charts into a clean `year_review_YYYY.md` file located in the `out/` folder.


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
Create a virtual environment and install the dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install garminconnect pandas numpy matplotlib seaborn
```

### 3. Run
Pass the years you want to generate reports for as arguments:
```bash
python generate_review.py 2024 2025
```
The output, including images and the Markdown document, will be created in the `out/` folder.
