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
DATA_DIR = 'data'

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

def get_year_colors(year_1, year_2):
    return {
        str(year_1): "#3463c1", 
        str(year_2): '#e74c3c'  
    }

def load_garmin_credentials():
    if not os.path.exists(GARMIN_CONFIG_FILE):
        print(f"Error: '{GARMIN_CONFIG_FILE}' missing.")
        sys.exit(1)
    with open(GARMIN_CONFIG_FILE, 'r') as f:
        data = json.load(f)
        return data.get('email'), data.get('password')

def fetch_activities(year):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    cache_file = os.path.join(DATA_DIR, f'garmin_activities_{year}.json')
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
def generate_comparison_charts(df: pd.DataFrame, img_dir: str, year_1: int, year_2: int):
    if not os.path.exists(img_dir):
        os.makedirs(img_dir)
        
    year_colors = get_year_colors(year_1, year_2)
        
    print("Starting comparison chart generation...")

    # --- 1. MONTHLY VOLUME COMPARISON (GROUPED BAR) ---
    print("  -> Generating 1/5: Monthly Volume Comparison...")
    months_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_hrs = df.groupby(['year', 'month_name'])['duration_hours'].sum().unstack(level=0).fillna(0)
    monthly_hrs = monthly_hrs.reindex(months_order)
    
    fig, ax = plt.subplots(figsize=(12, 5), facecolor=CHART_BG)
    monthly_hrs.plot(kind='bar', color=[year_colors.get(y, '#000000') for y in monthly_hrs.columns], ax=ax, width=0.7)
    
    ax.set_title(f"Monthly Training Volume: {year_1} vs {year_2}", fontsize=16, weight='bold')
    ax.set_ylabel("Hours")
    ax.set_xlabel("")
    plt.xticks(rotation=0)
    plt.legend(title='Year')
    plt.savefig(f"{img_dir}/monthly_volume_comparison.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
    plt.close()

    # --- 2. CUMULATIVE HOURS (LINE CHART) ---
    print("  -> Generating 2/5: Cumulative Hours...")
    daily_hrs = df.groupby(['year', 'day_of_year'])['duration_hours'].sum().reset_index()
    pivot_daily = daily_hrs.pivot(index='day_of_year', columns='year', values='duration_hours').fillna(0)
    
    pivot_daily = pivot_daily.reindex(range(1, 366), fill_value=0)
    cum_hrs = pivot_daily.cumsum()

    fig, ax = plt.subplots(figsize=(12, 5), facecolor=CHART_BG)
    for year in cum_hrs.columns:
        ax.plot(cum_hrs.index, cum_hrs[year], label=str(year), color=year_colors.get(year, '#000000'), linewidth=2.5)
    
    ax.set_title("Cumulative Training Hours Over the Year", fontsize=16, weight='bold')
    ax.set_ylabel("Total Hours")
    ax.set_xlabel("Day of the Year")
    plt.legend(title='Year')
    plt.savefig(f"{img_dir}/cumulative_hours_comparison.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
    plt.close()

    # --- 3. SPORT DISTRIBUTION (100% STACKED BAR) ---
    print("  -> Generating 3/5: Sport Distribution Shift...")
    sport_year = df.groupby(['year', 'sport'])['duration_hours'].sum().unstack(fill_value=0)
    
    totals = sport_year.sum(axis=1)
    pct = sport_year.div(totals, axis=0)
    sports_to_keep = pct.columns[(pct >= 0.05).any()]
    
    clean_sport_year = sport_year[sports_to_keep].copy()
    clean_sport_year['Other'] = sport_year.drop(columns=sports_to_keep, errors='ignore').sum(axis=1)
    
    clean_pct = clean_sport_year.div(clean_sport_year.sum(axis=1), axis=0) * 100
    
    fig, ax = plt.subplots(figsize=(10, 4), facecolor=CHART_BG)
    clean_pct.plot(kind='barh', stacked=True, color=[get_sport_color(s) for s in clean_pct.columns], ax=ax, width=0.6)
    
    ax.set_title("Discipline Shift (Percentage of Total Time)", fontsize=16, weight='bold')
    ax.set_xlabel("% of Total Time")
    ax.set_ylabel("")
    plt.legend(title='Discipline', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.savefig(f"{img_dir}/sport_distribution_shift.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
    plt.close()

    # --- 4. DAILY CALORIC BURN (BOXPLOT) ---
    print("  -> Generating 4/5: Daily Caloric Boxplot...")
    daily_cal = df.groupby(['year', df['start_time'].dt.date])['calories'].sum().reset_index()
    daily_cal = daily_cal[daily_cal['calories'] > 0]

    fig, ax = plt.subplots(figsize=(8, 6), facecolor=CHART_BG)
    sns.boxplot(
        x='year', 
        y='calories', 
        hue='year', 
        data=daily_cal, 
        palette=year_colors, 
        ax=ax, 
        width=0.5, 
        legend=False
    )
    
    ax.set_title("Distribution of Active Calories per Workout Day", fontsize=16, weight='bold')
    ax.set_ylabel("Active Calories")
    ax.set_xlabel("Year")
    plt.savefig(f"{img_dir}/daily_calories_boxplot.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
    plt.close()

    # --- 5. CYCLING PROGRESSION SCATTER PLOT ---
    print("  -> Generating 5/5: Cycling Progression Scatter Plot...")
    cycling_df = df[df['sport'] == 'Cycling'].copy()
    
    if not cycling_df.empty:
        fig, ax = plt.subplots(figsize=(10, 6), facecolor=CHART_BG)
        
        c_year1 = cycling_df[cycling_df['year'] == str(year_1)]
        if not c_year1.empty:
            ax.scatter(
                c_year1['distance_km'], 
                c_year1['elevation_gain'], 
                color=year_colors[str(year_1)], 
                alpha=0.5, 
                edgecolor='white',
                label=str(year_1)
            )
        
        c_year2 = cycling_df[cycling_df['year'] == str(year_2)]
        if not c_year2.empty:
            ax.scatter(
                c_year2['distance_km'], 
                c_year2['elevation_gain'], 
                color=year_colors[str(year_2)], 
                alpha=0.7, 
                edgecolor='white',
                label=str(year_2)
            )
        
        ax.set_title("Cycling Progression: Distance vs. Elevation", fontsize=16, weight='bold')
        ax.set_xlabel("Distance (km)")
        ax.set_ylabel("Elevation Gain (m)")
        
        ax.grid(True, linestyle='--', alpha=0.7)
        plt.legend(title='Year', loc='upper left')
        
        plt.savefig(f"{img_dir}/cycling_progression_scatter.png", dpi=150, facecolor=CHART_BG, bbox_inches='tight')
        plt.close()

    print("Comparison charts generated successfully.")

# ==========================================
# MARKDOWN GENERATOR
# ==========================================
def generate_comparison_markdown(df: pd.DataFrame, output_md: str, year_1: int, year_2: int):
    
    # --- Metrics Calculation ---
    stats = {}
    for y in [str(year_1), str(year_2)]:
        d = df[df['year'] == y]
        stats[y] = {
            'hours': d['duration_hours'].sum(),
            'activities': len(d),
            'distance': d['distance_km'].sum(),
            'elevation': d['elevation_gain'].sum(),
            'calories': d['calories'].sum()
        }

    # --- Streaks Calculation ---
    rest_days = {}
    max_active = {}
    max_off = {}
    
    for y in [str(year_1), str(year_2)]:
        df_y = df[df['year'] == y]
        active_dates = pd.Series(df_y['start_time'].dt.date.unique()).sort_values()
        full_year_dates = pd.date_range(start=f'{y}-01-01', end=f'{y}-12-31').date
        
        is_active = pd.Series(full_year_dates).isin(active_dates)
        
        rest_days[y] = int((~is_active).sum())
        
        active_groups = (~is_active).cumsum()
        max_active[y] = int(is_active.groupby(active_groups).sum().max()) if not is_active.empty else 0
        
        inactive_groups = is_active.cumsum()
        max_off[y] = int((~is_active).groupby(inactive_groups).sum().max()) if not is_active.empty else 0

    def calc_delta(val1, val2):
        if val1 == 0: return "+∞%"
        delta = ((val2 - val1) / val1) * 100
        sign = "+" if delta > 0 else ""
        return f"{sign}{delta:.1f}%"

    md = []
    
    md.append(f"# Year over Year Comparison: {year_1} vs {year_2}\n")
    
    md.append("## YoY Core Metrics\n")
    md.append(f"| Metric | {year_1} | {year_2} | Delta |")
    md.append(f"| :--- | :--- | :--- | :--- |")
    md.append(f"| **Total Time** | {stats[str(year_1)]['hours']:.1f} h | {stats[str(year_2)]['hours']:.1f} h | {calc_delta(stats[str(year_1)]['hours'], stats[str(year_2)]['hours'])} |")
    md.append(f"| **Activities** | {stats[str(year_1)]['activities']} | {stats[str(year_2)]['activities']} | {calc_delta(stats[str(year_1)]['activities'], stats[str(year_2)]['activities'])} |")
    md.append(f"| **Distance** | {stats[str(year_1)]['distance']:.0f} km | {stats[str(year_2)]['distance']:.0f} km | {calc_delta(stats[str(year_1)]['distance'], stats[str(year_2)]['distance'])} |")
    md.append(f"| **Elevation** | {stats[str(year_1)]['elevation']:.0f} m | {stats[str(year_2)]['elevation']:.0f} m | {calc_delta(stats[str(year_1)]['elevation'], stats[str(year_2)]['elevation'])} |")
    md.append(f"| **Active Calories** | {stats[str(year_1)]['calories']:,.0f} kcal | {stats[str(year_2)]['calories']:,.0f} kcal | {calc_delta(stats[str(year_1)]['calories'], stats[str(year_2)]['calories'])} |\n")

    md.append("## Consistency & Recovery\n")
    md.append(f"| Metric | {year_1} | {year_2} | Delta |")
    md.append(f"| :--- | :--- | :--- | :--- |")
    md.append(f"| **Full Rest Days** | {rest_days[str(year_1)]} | {rest_days[str(year_2)]} | {calc_delta(rest_days[str(year_1)], rest_days[str(year_2)])} |")
    md.append(f"| **Longest Active Streak** | {max_active[str(year_1)]} days | {max_active[str(year_2)]} days | {calc_delta(max_active[str(year_1)], max_active[str(year_2)])} |")
    md.append(f"| **Longest Off Streak** | {max_off[str(year_1)]} days | {max_off[str(year_2)]} days | {calc_delta(max_off[str(year_1)], max_off[str(year_2)])} |\n")

    # --- TOP 5 SPORTS BREAKDOWN ---
    md.append("## YoY Metrics by Top 5 Disciplines\n")
    
    top_sports = df.groupby('sport')['duration_hours'].sum().nlargest(5).index.tolist()
    
    for sport in top_sports:
        df_sport = df[df['sport'] == sport]
        df1_s = df_sport[df_sport['year'] == str(year_1)]
        df2_s = df_sport[df_sport['year'] == str(year_2)]
        
        s1_hrs = df1_s['duration_hours'].sum()
        s2_hrs = df2_s['duration_hours'].sum()
        
        s1_act = len(df1_s)
        s2_act = len(df2_s)
        
        s1_avg_dur = (s1_hrs / s1_act) if s1_act > 0 else 0
        s2_avg_dur = (s2_hrs / s2_act) if s2_act > 0 else 0
        
        s1_dist = df1_s['distance_km'].sum()
        s2_dist = df2_s['distance_km'].sum()
        
        s1_elev = df1_s['elevation_gain'].sum()
        s2_elev = df2_s['elevation_gain'].sum()
        
        s1_cal = df1_s['calories'].sum()
        s2_cal = df2_s['calories'].sum()
        
        md.append(f"### {sport}\n")
        md.append(f"| Metric | {year_1} | {year_2} | Delta |")
        md.append(f"| :--- | :--- | :--- | :--- |")
        
        if (s1_hrs + s2_hrs) > 0:
            md.append(f"| **Total Time** | {s1_hrs:.1f} h | {s2_hrs:.1f} h | {calc_delta(s1_hrs, s2_hrs)} |")
            
        if (s1_act + s2_act) > 0:
            md.append(f"| **Activities** | {s1_act} | {s2_act} | {calc_delta(s1_act, s2_act)} |")
            
        if (s1_avg_dur + s2_avg_dur) > 0:
            md.append(f"| **Avg. Duration** | {s1_avg_dur:.1f} h | {s2_avg_dur:.1f} h | {calc_delta(s1_avg_dur, s2_avg_dur)} |")
            
        if (s1_dist + s2_dist) > 0:
            md.append(f"| **Distance** | {s1_dist:.0f} km | {s2_dist:.0f} km | {calc_delta(s1_dist, s2_dist)} |")
            
        if (s1_elev + s2_elev) > 0:
            md.append(f"| **Elevation** | {s1_elev:.0f} m | {s2_elev:.0f} m | {calc_delta(s1_elev, s2_elev)} |")
            
        if (s1_cal + s2_cal) > 0:
            md.append(f"| **Active Calories** | {s1_cal:,.0f} kcal | {s2_cal:,.0f} kcal | {calc_delta(s1_cal, s2_cal)} |\n")
        
        md.append("\n")

    # --- CHARTS SECTION ---
    md.append("## Cumulative Training Hours Over the Year\n")
    md.append(f"![Cumulative Hours](images/cumulative_hours_comparison.png)\n")

    md.append("## Monthly Training Volume Comparison\n")
    md.append(f"![Monthly Volume](images/monthly_volume_comparison.png)\n")

    md.append("## Discipline Shift (Percentage of Total Time)\n")
    md.append(f"![Sport Distribution Shift](images/sport_distribution_shift.png)\n")

    md.append("## Distribution of Active Calories per Workout Day\n")
    md.append(f"![Daily Calories Boxplot](images/daily_calories_boxplot.png)\n")

    md.append("## Cycling Progression: Pushing the Limits\n")
    md.append(f"![Cycling Progression Scatter](images/cycling_progression_scatter.png)\n")

    md.append("---\n*Generated via Python using raw data from the Garmin API.*")
    
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
    
    print(f"Markdown created successfully: {output_md}")

def main():
    parser = argparse.ArgumentParser(description="Compare Garmin data across two years")
    parser.add_argument('year1', type=int, help='First year to compare (e.g., 2024)')
    parser.add_argument('year2', type=int, help='Second year to compare (e.g., 2025)')
    args = parser.parse_args()
    
    year_1 = args.year1
    year_2 = args.year2

    if not os.path.exists(OUT_BASE_DIR):
        os.makedirs(OUT_BASE_DIR)

    raw_data_1 = fetch_activities(year_1)
    raw_data_2 = fetch_activities(year_2)

    if not raw_data_1 or not raw_data_2:
        print("Missing data for one or both years. Cannot compare.")
        return

    df1 = pd.DataFrame(raw_data_1)
    df1['year'] = str(year_1)
    
    df2 = pd.DataFrame(raw_data_2)
    df2['year'] = str(year_2)
    
    df = pd.concat([df1, df2], ignore_index=True).copy()

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
    
    df['start_time'] = pd.to_datetime(df['startTimeLocal'])
    df['month_name'] = df['start_time'].dt.strftime('%b')
    df['day_of_year'] = df['start_time'].dt.dayofyear

    comp_dir = os.path.join(OUT_BASE_DIR, f"{year_1}_vs_{year_2}")
    img_dir = os.path.join(comp_dir, 'images')
    output_md = os.path.join(comp_dir, f'comparison_{year_1}_vs_{year_2}.md')

    generate_comparison_charts(df, img_dir, year_1, year_2)
    generate_comparison_markdown(df, output_md, year_1, year_2)

if __name__ == '__main__':
    main()