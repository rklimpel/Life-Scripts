import os
import json
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Headless mode for macOS
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from garminconnect import Garmin

# ==========================================
# CONFIGURATION & STYLING
# ==========================================
TARGET_YEAR = 2025
GARMIN_CONFIG_FILE = 'garmin_config.json'
CACHE_FILE = f'garmin_activities_{TARGET_YEAR}.json'
OUTPUT_MD = f'year_review_{TARGET_YEAR}.md'
IMG_DIR = 'images'

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

def fetch_activities():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)

    print("No cache found. Fetching from Garmin...")
    email, password = load_garmin_credentials()
    client = Garmin(email, password)
    client.login()

    activities = client.get_activities_by_date(f"{TARGET_YEAR}-01-01", f"{TARGET_YEAR}-12-31")
    with open(CACHE_FILE, 'w') as f:
        json.dump(activities, f)
    return activities

def get_sport_color(sport):
    return SPORT_COLORS.get(sport, '#34495e')

# ==========================================
# VISUALIZATION (CHARTS)
# ==========================================
def generate_charts(df: pd.DataFrame):
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)
        
    print("Starting chart generation...")

    # --- 1. DONUT CHART ---
    print("  -> Generating 1/4: Donut Chart (Sport Distribution)...")
    total_hours = df['duration_hours'].sum()
    sport_hours = df.groupby('sport')['duration_hours'].sum()
    sport_hours_pct = sport_hours / total_hours
    
    # Everything under 5% becomes "Other"
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
    plt.savefig(f"{IMG_DIR}/sport_distribution_donut.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
    plt.close()

    # --- 2. LINE CHART ---
    print("  -> Generating 2/4: Line Chart (Calorie Balance)...")
    full_year = pd.date_range(start=f'{TARGET_YEAR}-01-01', end=f'{TARGET_YEAR}-12-31')
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
    plt.savefig(f"{IMG_DIR}/calorie_burn_trend.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
    plt.close()

    # --- 3. HEATMAP ---
    print("  -> Generating 3/4: Heatmap (Time of Day & Duration)...")
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
        plt.savefig(f"{IMG_DIR}/time_of_day_heatmap.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
        plt.close()

    # --- 4. STACKED BAR CHART (MONTHLY PROGRESSION) ---
    print("  -> Generating 4/4: Bar Chart (Monthly Progression)...")
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
    plt.savefig(f"{IMG_DIR}/monthly_stacked_bar.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
    plt.close()

    print("Charts generated successfully.")

# ==========================================
# MARKDOWN GENERATOR
# ==========================================
def generate_markdown(df: pd.DataFrame):
    total_hours = df['duration_hours'].sum()
    total_activities = len(df)
    total_distance_km = df['distance_km'].sum()
    total_active_calories = df['calories'].sum()
    total_elevation = df['elevation_gain'].sum()
    
    # Calculate consistency metrics
    active_dates = pd.Series(df['start_time'].dt.date.unique()).sort_values()
    full_year_dates = pd.date_range(start=f'{TARGET_YEAR}-01-01', end=f'{TARGET_YEAR}-12-31').date
    
    rest_days = len(full_year_dates) - len(active_dates)
    
    # Calculate longest streak
    is_active = pd.Series(full_year_dates).isin(active_dates)
    streak_groups = (~is_active).cumsum()
    max_streak = is_active.groupby(streak_groups).sum().max()
    
    # Highlights
    longest_dur = df.loc[df['duration_hours'].idxmax()]
    longest_dist = df.loc[df['distance_km'].idxmax()]
    most_cals = df.loc[df['calories'].idxmax()]

    # Cycling specific highlights (only 'Cycling')
    cycling_df = df[df['sport'] == 'Cycling']
    fastest_ride = None
    
    if not cycling_df.empty:
        valid_speed_rides = cycling_df[cycling_df['distance_km'] >= 50.0]
        if not valid_speed_rides.empty:
            fastest_ride = valid_speed_rides.loc[valid_speed_rides['average_speed_kmh'].idxmax()]

    md = []
    md.append(f"# {TARGET_YEAR} Year in Review: Basketball & Endurance\n")
    md.append(f"Sport in {TARGET_YEAR} was characterized by a clear split: the basketball season in the 1. Regionalliga and building aerobic base endurance on the bike. With the addition of a road bike to my gravel setup, the focus shifted toward longer distances and early steps into ultra-bikepacking.\n")
    
    md.append("## 📊 Annual Statistics\n")
    md.append(f"| Total Time | Activities | Total Distance | Elevation Gain | Active Calories |")
    md.append(f"| :--- | :--- | :--- | :--- | :--- |")
    md.append(f"| **{total_hours:.1f} h** | **{total_activities}** | **{total_distance_km:.0f} km** | **{total_elevation:.0f} m** | **{total_active_calories:,.0f} kcal** |\n")

    md.append("### Consistency & Recovery")
    md.append(f"- **Longest Active Streak:** {int(max_streak)} days")
    md.append(f"- **Full Rest Days:** {rest_days} days\n")

    md.append("## 🏆 Season Highlights\n")
    md.append(f"- ⏱️ **Longest Workout:** {longest_dur['duration_hours']:.1f} h on {longest_dur['start_time'].strftime('%m/%d')} ({longest_dur['sport']})")
    if longest_dist['distance_km'] > 0:
        md.append(f"- 📏 **Max Distance:** {longest_dist['distance_km']:.1f} km on {longest_dist['start_time'].strftime('%m/%d')} ({longest_dist['sport']})")
    md.append(f"- 🔥 **Highest Burn:** {most_cals['calories']:.0f} kcal in a single session on {most_cals['start_time'].strftime('%m/%d')}")
    if fastest_ride is not None:
        md.append(f"- 🚀 **Fastest Ride (>50km):** {fastest_ride['average_speed_kmh']:.1f} km/h avg over {fastest_ride['distance_km']:.1f} km on {fastest_ride['start_time'].strftime('%m/%d')}\n")

    md.append("## 📈 Calorie Balance & Training Load")
    md.append("This chart shows training calories stacked on top of the daily resting metabolic rate (~2,450 kcal). The red trend line (14-day average) visualizes intensity control: heavy training blocks alternating with necessary tapering and recovery phases.\n")
    md.append(f"![Calorie Trend]({IMG_DIR}/calorie_burn_trend.png)\n")

    md.append("## ⏰ Training Rhythm")
    md.append("The distribution of load throughout the week follows a fixed pattern: Team practices in the gym take up the late evening hours during the week. Weekends are primarily used for long endurance rides.\n")
    md.append(f"![Time of Day Heatmap]({IMG_DIR}/time_of_day_heatmap.png)\n")

    md.append("## 📉 Discipline Distribution\n")
    md.append("Training volume is primarily split between Basketball and Cycling. Everyday bike commuting is tracked separately. Supplementary strength training serves injury prevention and athleticism.\n")
    md.append(f"![Monthly Progression]({IMG_DIR}/monthly_stacked_bar.png)\n")
    md.append(f"![Donut Chart]({IMG_DIR}/sport_distribution_donut.png)\n")

    md.append("---\n*Generated via Python using raw data from the Garmin API.*")
    
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
    
    print(f"Markdown created successfully: {OUTPUT_MD}")

def main():
    raw_data = fetch_activities()
    if not raw_data:
        return

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

    generate_charts(df)
    generate_markdown(df)

if __name__ == '__main__':
    main()