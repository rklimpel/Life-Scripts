import os
import json
import sys
from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from garminconnect import Garmin

# ==========================================
# KONFIGURATION
# ==========================================
DRY_RUN = False  

SEARCH_START_DATE = "2025-12-11"
SEARCH_END_DATE = "2025-12-31"

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
SYNC_STATE_FILE = 'synced_events.json'
GARMIN_CONFIG_FILE = 'garmin-credentials.json'

FALLBACK_WEIGHT_KG = 100.0  

# ==========================================
# HILFSFUNKTIONEN
# ==========================================

def load_garmin_credentials():
    if not os.path.exists(GARMIN_CONFIG_FILE):
        print(f"Fehler: Die Datei '{GARMIN_CONFIG_FILE}' wurde nicht gefunden.")
        sys.exit(1)
    with open(GARMIN_CONFIG_FILE, 'r') as f:
        data = json.load(f)
        return data.get('email'), data.get('password')

def is_game_event(summary: str) -> bool:
    return "(Heim)" in summary or "(Auswärts)" in summary

def is_basketball_event(summary: str) -> bool:
    if not summary:
        return False
    keywords = ["🏀", "Basketballtraining", "Basketball", "(Heim)", "(Auswärts)"]
    return any(keyword in summary for keyword in keywords)

def get_garmin_weight(garmin_client, date_iso: str) -> float:
    """Holt das Gewicht (Body Composition) für den spezifischen Tag."""
    try:
        body_comp = garmin_client.get_body_composition(date_iso)
        
        if body_comp and isinstance(body_comp, dict):
            if 'totalAverage' in body_comp and 'weight' in body_comp['totalAverage']:
                weight_val = body_comp['totalAverage']['weight']
                
                # FIX: Prüfen, ob der Wert nicht 'None' (null in JSON) ist
                if weight_val is not None:
                    weight = float(weight_val)
                    if weight > 300: 
                        weight = weight / 1000.0
                    return weight
                
    except Exception as e:
        print(f"  [Warnung] Konnte Gewicht aus Body Composition nicht abrufen. Fehler: {e}")
    
    return FALLBACK_WEIGHT_KG

def calculate_base_calories(summary: str, duration_minutes: float, weight_kg: float) -> float:
    """Berechnet Kalorien basierend auf prozentualer Zeiteinteilung und dynamischem Gewicht."""
    if is_game_event(summary):
        # Prozentuale Aufteilung der Brutto-Zeit für realistischere Skalierung
        warmup_mins = duration_minutes * 0.35
        game_mins = duration_minutes * 0.20
        rest_mins = duration_minutes * 0.45
        
        cal_warmup = (warmup_mins / 60.0) * 6.0 * weight_kg
        cal_game = (game_mins / 60.0) * 10.0 * weight_kg
        cal_rest = (rest_mins / 60.0) * 2.5 * weight_kg
        
        return cal_warmup + cal_game + cal_rest
    else:
        # Standard-Training 1. Regio (8.0 MET)
        return (duration_minutes / 60.0) * 8.0 * weight_kg

def get_post_workout_intensity_multiplier(garmin_client, end_dt: datetime) -> float:
    """Feingranulare EPOC/Stress-Analyse für exaktere Multiplikatoren."""
    date_str = end_dt.strftime("%Y-%m-%d")
    
    try:
        stress_data = garmin_client.get_stress_data(date_str)
        if not isinstance(stress_data, dict):
            return 1.0
        stress_values = stress_data.get('stressValuesArray', [])
    except Exception as e:
        print(f"  [Warnung] Konnte Stress-Daten nicht abrufen: {e}")
        return 1.0

    if not stress_values:
        print(f"  [Warnung] Konnte Stress-Daten nicht abrufen. No Stress values array.")
        return 1.0

    start_ms = int(end_dt.timestamp() * 1000)
    end_ms = int((end_dt.timestamp() + (2 * 3600)) * 1000)

    revelant_stress_scores = [
        point[1] for point in stress_values 
        if len(point) >= 2 and point[1] > 0 and start_ms <= point[0] <= end_ms
    ]

    if len(revelant_stress_scores) < 10:
        print("  [Intensität] Zu wenig Stress-Daten gefunden (Uhr evtl. zu spät angelegt). Multiplikator: 1.0")
        return 1.0

    avg_stress = sum(revelant_stress_scores) / len(revelant_stress_scores)
    
    if avg_stress > 70:
        mult = 1.20
    elif avg_stress > 55:
        mult = 1.10
    elif avg_stress > 40:
        mult = 1.00
    elif avg_stress > 25:
        mult = 0.90
    else:
        mult = 0.80

    print(f"  [Intensität] Ø Stress nach Belastung: {int(avg_stress)}. Multiplikator: {mult}")
    return mult

def load_synced_ids() -> set:
    if os.path.exists(SYNC_STATE_FILE):
        with open(SYNC_STATE_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_synced_id(event_id: str):
    synced = load_synced_ids()
    synced.add(event_id)
    with open(SYNC_STATE_FILE, 'w') as f:
        json.dump(list(synced), f)

def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

# ==========================================
# HAUPTPROGRAMM
# ==========================================

def main():
    if DRY_RUN:
        print("=== DRY RUN MODUS IST AKTIV ===\n")
    
    print("Lade Garmin Credentials und initialisiere Client...")
    garmin_email, garmin_password = load_garmin_credentials()
    garmin_client = Garmin(garmin_email, garmin_password)
    garmin_client.login()

    print("Initialisiere Google Calendar API...")
    service = get_calendar_service()
    synced_ids = load_synced_ids()

    now = datetime.now(timezone.utc)
    if SEARCH_START_DATE and SEARCH_END_DATE:
        start_dt_user = datetime.strptime(SEARCH_START_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt_user = datetime.strptime(SEARCH_END_DATE, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        time_min = start_dt_user.isoformat()
        time_max = end_dt_user.isoformat()
    else:
        time_min = (now - timedelta(days=7)).isoformat()
        time_max = now.isoformat()

    print(f"Suche Termine von {time_min} bis {time_max}...\n")
    
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])

    if not events:
        print("Keine relevanten Termine gefunden.")
        return

    for event in events:
        event_id = event['id']
        summary = event.get('summary', '')

        if event_id in synced_ids or not is_basketball_event(summary):
            continue

        start_str = event['start'].get('dateTime')
        end_str = event['end'].get('dateTime')

        if not start_str or not end_str:
            continue

        # Parse und korrigiere Timezone (lokale Zeit für Garmin Upload)
        start_dt_utc = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        end_dt_utc = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        
        start_dt_local = start_dt_utc.astimezone()
        end_dt_local = end_dt_utc.astimezone()
        
        duration_sec = int((end_dt_utc - start_dt_utc).total_seconds())
        duration_min = duration_sec / 60.0
        date_iso = start_dt_local.strftime("%Y-%m-%d")
        
        event_type_str = "SPIEL" if is_game_event(summary) else "TRAINING"
        print(f"\n--- Verarbeite [{event_type_str}]: {summary} ({start_dt_local.strftime('%d.%m.%Y %H:%M')}) ---")
        
        # 1. Gewicht abrufen
        current_weight = get_garmin_weight(garmin_client, date_iso)
        print(f"  [Körperdaten] Berechne mit {current_weight} kg.")

        # 2. Basis-Kalorien berechnen
        base_calories = calculate_base_calories(summary, duration_min, current_weight)
        
        # 3. Multiplikator über Garmin Stress-Daten ermitteln
        multiplier = get_post_workout_intensity_multiplier(garmin_client, end_dt_utc)

        # 4. Finale Kalorien
        final_calories = int(base_calories * multiplier)
        
        print(f"  -> Dauer: {int(duration_min)} Min, Basis: {int(base_calories)} kcal, Final: {final_calories} kcal")

        if not DRY_RUN:
            try:
                # Wir bauen das Payload exakt wie in der Library auf, aber mit unseren Anpassungen
                payload = {
                    "activityTypeDTO": {"typeKey": "basketball"},
                    "accessControlRuleDTO": {"typeId": 2, "typeKey": "private"},
                    "timeZoneUnitDTO": {"unitKey": "Europe/Berlin"},
                    "activityName": summary,
                    "metadataDTO": {
                        "autoCalcCalories": False, # WICHTIG: Überschreibt den Garmin-Standard
                    },
                    "summaryDTO": {
                        "startTimeLocal": start_dt_local.strftime("%Y-%m-%dT%H:%M:%S.000"),
                        "distance": 0.0,
                        "duration": float(duration_sec),
                        "calories": float(final_calories) # WICHTIG: Unsere berechneten Kalorien
                    },
                }

                # Nutzt die zugrundeliegende Methode der Library
                garmin_client.create_manual_activity_from_json(payload)
                
                save_synced_id(event_id)
                print("  -> Erfolg: Aktivität bei Garmin eingetragen.")
            except Exception as e:
                print(f"  -> Fehler beim Upload: {e}")

if __name__ == '__main__':
    main()