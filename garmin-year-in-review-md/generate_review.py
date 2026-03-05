import os
import json
import sys
import argparse
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Headless mode for macOS
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

from garminconnect import Garmin

# ==========================================
# CONFIGURATION & STYLING
# ==========================================
GARMIN_CONFIG_FILE = 'garmin_config.json'
OUT_BASE_DIR = 'out'

BASE_RESTING_CALORIES = 2450  

sns.set_theme(style="whitegrid")
CHART_BG = '#ffffff'

# Mapping Garmin keys to clean English labels
SPORT_MAPPING = {
    'basketball': 'Basketball',
    'road_biking': 'Cycling',
    'gravel_cycling': 'Cycling',
    'cycling': 'Commuting (Bike)', 
    'running': 'Running',
    'strength_training': 'Strength',
    'virtual_ride': 'Virtual Cycling',
    'walking': 'Walking/Hiking',
    'hiking': 'Walking/Hiking'
}

SPORT_COLORS = {
    'Basketball': '#e67e22',
    'Cycling': '#3498db',
    'Commuting (Bike)': '#85c1e9',
    'Running': '#2ecc71',
    'Strength': '#e74c3c',
    'Other': '#95a5a6',
    'Walking/Hiking': '#f1c40f'
}

def load_garmin_credentials():
    if not os.path.exists(GARMIN_CONFIG_FILE):
        print(f"Error: '{GARMIN_CONFIG_FILE}' missing.")
        sys.exit(1)
    with open(GARMIN_CONFIG_FILE, 'r') as f:
        data = json.load(f)
        return data.get('email'), data.get('password')

def fetch_activities(year):
    cache_file = f'garmin_activities_{year}.json'
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)

    print(f"No cache found for {year}. Fetching from Garmin...")
    email, password = load_garmin_credentials()
    client = Garmin(email, password)
    client.login()

    activities = client.get_activities_by_date(f"{year}-01-01", f"{year}-12-31")
    with open(cache_file, 'w') as f:
        json.dump(activities, f)
    return activities

def get_sport_color(sport):
    return SPORT_COLORS.get(sport, '#34495e')

# ==========================================
# VISUALIZATION (CHARTS)
# ==========================================
def generate_charts(df: pd.DataFrame, year: int, img_dir: str):
    if not os.path.exists(img_dir):
        os.makedirs(img_dir)
        
    print(f"[{year}] Starting chart generation...")

    # --- 1. DONUT CHART ---
    print(f"  -> [{year}] Generating 1/4: Donut Chart...")
    total_hours = df['duration_hours'].sum()
    sport_hours = df.groupby('sport')['duration_hours'].sum()
    sport_hours_pct = sport_hours / total_hours
    
    sports_to_keep = sport_hours_pct[sport_hours_pct >= 0.05].index
    df['sport_donut'] = df['sport'].where(df['sport'].isin(sports_to_keep), 'Other')
    donut_data = df.groupby('sport_donut')['duration_hours'].sum().sort_values(ascending=False)
    
    fig, ax = plt.subplots(figsize=(8, 8), facecolor=CHART_BG)
    ax.pie(
        donut_data, 
        labels=donut_data.index, 
        autopct='%1.1f%%', 
        startangle=90, 
        colors=[get_sport_color(s) for s in donut_data.index],
        wedgeprops=dict(width=0.3, edgecolor='w')
    )
    ax.set_title(f"Training Time by Discipline (Cut-off < 5%)", fontsize=16, weight='bold')
    plt.savefig(f"{img_dir}/sport_distribution_donut.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
    plt.close()

    # --- 2. LINE CHART ---
    print(f"  -> [{year}] Generating 2/4: Line Chart...")
    full_year = pd.date_range(start=f'{year}-01-01', end=f'{year}-12-31')
    daily_cal = df.groupby(df['start_time'].dt.date)['calories'].sum().reset_index()
    daily_cal['start_time'] = pd.to_datetime(daily_cal['start_time'])
    daily_cal.set_index('start_time', inplace=True)
    daily_cal = daily_cal.reindex(full_year, fill_value=0)
    
    daily_cal['total_calories'] = daily_cal['calories'] + BASE_RESTING_CALORIES
    daily_cal['rolling_14d_total'] = daily_cal['total_calories'].rolling(window=14, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(12, 5), facecolor=CHART_BG)
    ax.fill_between(daily_cal.index, 0, BASE_RESTING_CALORIES, color='#ecf0f1', label='Resting Metabolic Rate (~2,450 kcal)')
    ax.bar(daily_cal.index, daily_cal['calories'], bottom=BASE_RESTING_CALORIES, color='#e67e22', alpha=0.7, label='Active Calories')
    ax.plot(daily_cal.index, daily_cal['rolling_14d_total'], color='#c0392b', linewidth=2.5, label='14-Day Trend')
    
    ax.set_title("Calorie Balance: Total Expenditure & Training", fontsize=16, weight='bold')
    ax.set_ylabel("Total kcal / Day")
    plt.legend(loc='upper left')
    plt.savefig(f"{img_dir}/calorie_burn_trend.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
    plt.close()

    # --- 3. HEATMAP ---
    print(f"  -> [{year}] Generating 3/4: Heatmap...")
    heatmap_records = []
    for _, row in df.iterrows():
        start = row['start_time']
        duration_sec = row['duration']
        end = start + pd.Timedelta(seconds=duration_sec)
        
        curr = start
        while curr < end:
            next_hour = curr.floor('h') + pd.Timedelta(hours=1)
            if next_hour > end:
                next_hour = end
            
            chunk_hours = (next_hour - curr).total_seconds() / 3600.0
            if chunk_hours > 0:
                heatmap_records.append({
                    'weekday': curr.dayofweek,
                    'weekday_name': curr.strftime('%a'),
                    'hour': curr.hour,
                    'duration_hours': chunk_hours
                })
            curr = next_hour

    if heatmap_records:
        df_heatmap = pd.DataFrame(heatmap_records)
        heatmap_pivot = df_heatmap.groupby(['weekday_name', 'hour'])['duration_hours'].sum().reset_index()
        heatmap_pivot = heatmap_pivot.pivot(index="weekday_name", columns="hour", values="duration_hours").fillna(0)
        
        for h in range(24):
            if h not in heatmap_pivot.columns:
                heatmap_pivot[h] = 0
        heatmap_pivot = heatmap_pivot[range(24)]
        
        weekdays_order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        heatmap_pivot = heatmap_pivot.reindex(weekdays_order)
        
        fig, ax = plt.subplots(figsize=(12, 5), facecolor=CHART_BG)
        sns.heatmap(heatmap_pivot, cmap="Blues", linewidths=0.5, linecolor='white', ax=ax, cbar_kws={'label': 'Training Hours'})
        ax.set_title("Training Time Distribution (Exact Duration per Hour)", fontsize=16, weight='bold')
        ax.set_ylabel("")
        ax.set_xlabel("Time of Day")
        plt.savefig(f"{img_dir}/time_of_day_heatmap.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
        plt.close()

    # --- 4. STACKED BAR CHART (MONTHLY PROGRESSION) ---
    print(f"  -> [{year}] Generating 4/4: Bar Chart...")
    months_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    df_pivot = df.pivot_table(index='month_name', columns='sport', values='duration_hours', aggfunc='sum', fill_value=0)
    df_pivot = df_pivot.reindex(months_order)
    
    fig, ax = plt.subplots(figsize=(12, 6), facecolor=CHART_BG)
    df_pivot.plot(kind='bar', stacked=True, color=[get_sport_color(s) for s in df_pivot.columns], ax=ax, width=0.8)
    
    ax.set_title("Monthly Training Hours by Discipline", fontsize=16, weight='bold')
    ax.set_ylabel("Hours")
    ax.set_xlabel("")
    plt.xticks(rotation=0)
    
    plt.legend(title='Discipline', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.savefig(f"{img_dir}/monthly_stacked_bar.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
    plt.close()

    print(f"[{year}] Charts generated successfully.")

# ==========================================
# MARKDOWN GENERATOR
# ==========================================
def generate_markdown(df: pd.DataFrame, year: int, output_md: str):
    total_hours = df['duration_hours'].sum()
    total_activities = len(df)
    total_distance_km = df['distance_km'].sum()
    total_active_calories = df['calories'].sum()
    total_elevation = df['elevation_gain'].sum()
    
    # Calculate consistency metrics
    active_dates = pd.Series(df['start_time'].dt.date.unique()).sort_values()
    full_year_dates = pd.date_range(start=f'{year}-01-01', end=f'{year}-12-31').date
    
    rest_days = len(full_year_dates) - len(active_dates)
    
    # Calculate longest streak
    is_active = pd.Series(full_year_dates).isin(active_dates)
    streak_groups = (~is_active).cumsum()
    max_streak = is_active.groupby(streak_groups).sum().max() if not is_active.empty else 0
    
    # Highlights
    longest_dur = df.loc[df['duration_hours'].idxmax()] if not df.empty else None
    longest_dist = df.loc[df['distance_km'].idxmax()] if not df.empty else None
    most_cals = df.loc[df['calories'].idxmax()] if not df.empty else None

    # Cycling specific highlights
    cycling_df = df[df['sport'] == 'Cycling']
    fastest_ride = None
    
    if not cycling_df.empty:
        valid_speed_rides = cycling_df[cycling_df['distance_km'] >= 50.0]
        if not valid_speed_rides.empty:
            fastest_ride = valid_speed_rides.loc[valid_speed_rides['average_speed_kmh'].idxmax()]

    md = []
    
    md.append(f"# {year} Year in Review: Basketball & Endurance\n")
    
    md.append("## Annual Statistics\n")
    md.append(f"| Total Time | Activities | Total Distance | Elevation Gain | Active Calories |")
    md.append(f"| :--- | :--- | :--- | :--- | :--- |")
    md.append(f"| **{total_hours:.1f} h** | **{total_activities}** | **{total_distance_km:.0f} km** | **{total_elevation:.0f} m** | **{total_active_calories:,.0f} kcal** |\n")

    md.append("### Consistency & Recovery\n")
    md.append(f"- **Longest Active Streak:** {int(max_streak)} days")
    md.append(f"- **Full Rest Days:** {rest_days} days\n")

    md.append("## Season Highlights\n")
    if longest_dur is not None:
        md.append(f"- ⏱️ **Longest Workout:** {longest_dur['duration_hours']:.1f} h on {longest_dur['start_time'].strftime('%m/%d')} ({longest_dur['sport']})")
    if longest_dist is not None and longest_dist['distance_km'] > 0:
        md.append(f"- 📏 **Max Distance:** {longest_dist['distance_km']:.1f} km on {longest_dist['start_time'].strftime('%m/%d')} ({longest_dist['sport']})")
    if most_cals is not None:
        md.append(f"- 🔥 **Highest Burn:** {most_cals['calories']:.0f} kcal in a single session on {most_cals['start_time'].strftime('%m/%d')}")
    if fastest_ride is not None:
        md.append(f"- 🚀 **Fastest Ride (>50km):** {fastest_ride['average_speed_kmh']:.1f} km/h avg over {fastest_ride['distance_km']:.1f} km on {fastest_ride['start_time'].strftime('%m/%d')}\n")

    md.append("## Calorie Balance: Total Expenditure & Training\n")
    md.append(f"![Calorie Trend](images/calorie_burn_trend.png)\n")

    md.append("## Training Time Distribution (Exact Duration per Hour)\n")
    md.append(f"![Time of Day Heatmap](images/time_of_day_heatmap.png)\n")

    md.append("## Monthly Training Hours by Discipline\n")
    md.append(f"![Monthly Progression](images/monthly_stacked_bar.png)\n")
    
    md.append("## Training Time by Discipline (Cut-off < 5%)\n")
    md.append(f"![Donut Chart](images/sport_distribution_donut.png)\n")

    md.append("---\n*Generated via Python using raw data from the Garmin API.*")
    
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
    
    print(f"[{year}] Markdown created successfully: {output_md}")

def process_year(year: int):
    raw_data = fetch_activities(year)
    if not raw_data:
        print(f"[{year}] No activities found.")
        return

    # Folder setup
    year_dir = os.path.join(OUT_BASE_DIR, str(year))
    img_dir = os.path.join(year_dir, 'images')
    output_md = os.path.join(year_dir, f'year_review_{year}.md')

    df = pd.DataFrame(raw_data)
    
    df['sport'] = df['activityType'].apply(
        lambda x: SPORT_MAPPING.get(x.get('typeKey', 'Other'), 'Other') 
        if isinstance(x, dict) else 'Other'
    )
    
    df['duration'] = df.get('duration', 0)
    df['duration_hours'] = df['duration'] / 3600.0
    
    df['distance_km'] = df.get('distance', 0) / 1000.0
    df['distance_km'] = df['distance_km'].fillna(0)
    
    df['calories'] = df.get('calories', 0)
    df['calories'] = df['calories'].fillna(0)
    
    df['elevation_gain'] = df.get('elevationGain', 0)
    df['elevation_gain'] = df['elevation_gain'].fillna(0)

    df['average_speed_kmh'] = df.get('averageSpeed', 0) * 3.6
    df['average_speed_kmh'] = df['average_speed_kmh'].fillna(0)
    
    df['start_time'] = pd.to_datetime(df['startTimeLocal'])
    df['month_name'] = df['start_time'].dt.strftime('%b')

    generate_charts(df, year, img_dir)
    generate_markdown(df, year, output_md)

def main():
    if not os.path.exists(OUT_BASE_DIR):
    parser = argparse.ArgumentParser(description="Generate Garmin Year in Review")
    parser.add_argument('years', type=int, nargs='+', help='Years to process (e.g., 2023 2024)')
    args = parser.parse_args()

    if not os.path.exists(OUT_BASE_DIR):
        os.makedirs(OUT_BASE_DIR)

    for year in args.years
        print(f"Processing Year: {year}")
        print(f"{'='*40}")
        process_year(year)

if __name__ == '__main__':
    main()