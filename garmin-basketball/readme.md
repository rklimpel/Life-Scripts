# Calender to Garmin Basketball Auto-Sync 🏀

A Python automation script that reads basketball practices and games from Google Calendar and automatically logs them as manual activities in Garmin Connect. 

## The Problem
Wearing a Garmin watch during competitive basketball is a no-go – it's dangerous and usually not allowed. However, I still want my total activity count, time and active calories tracked halfway accurately in Garmin Connect. Manually calculating calories and entering every single practice or game into the Garmin app is tedious and inefficient.

## The Solution
This script automates the entire workflow:
1. **Reads Google Calendar:** Looks for specific keywords (like "🏀", "Basketballtraining", "(Heim)", "(Auswärts)") in my primary calendar.
2. **Calculates Calories (Science-Based):** Uses standard MET (Metabolic Equivalent of Task) formulas combined with my current body weight fetched from Garmin. It distinguishes between standard practice and game days (applying a dynamic split for warmup, high-intensity game time, and bench rest).
3. **Intensity Adjustment (EPOC):** Since I put my watch back on after showering, the script fetches my Garmin HRV/Stress data for the 2 hours after the workout. Based on the post-exercise physiological stress (EPOC), it applies a multiplier (0.8x to 1.2x) to fine-tune the burned calories.
4. **Pushes to Garmin:** Uploads the activity directly to Garmin Connect, bypassing Garmin's inaccurate default calorie auto-calculation for manual workouts.

## Why it works (Under the Hood)
This project relies on the `garminconnect` Python library, which essentially impersonates the Garmin Connect web dashboard. 

## How to use it

### 1. Prerequisites
* Python 
* A Google Cloud Project with the **Google Calendar API** enabled.
* Download your OAuth 2.0 Client ID as `credentials.json` and place it in the project root.
* Setup `garmin-credentials.json` with garmin user login data

### 2. Setup
Create a virtual environment and install the dependencies to avoid macOS system-package conflicts:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install garminconnect google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 3. Run
Run that stuff with python.