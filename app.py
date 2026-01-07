import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Metro Sharon CBB Draft Leaderboard", layout="wide")
st.title("Metro Sharon CBB Draft Leaderboard")

# --- HELPER FUNCTIONS ---
def safe_int(value):
    """Convert score to int or return None"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

@st.cache_data(ttl=3600)
def load_draft_picks():
    # Updated ESPN team IDs (replace with real IDs from ESPN API)
    columns = ["team_id", "team_name", "person"]
    draft = [
        # Doug
        [250, "Saint Louis", "Doug"],
        [225, "Virginia", "Doug"],
        [110, "Cincinnati", "Doug"],
        [240, "Providence", "Doug"],
        [100, "Illinois", "Doug"],
        [80, "Florida", "Doug"],
        [120, "Gonzaga", "Doug"],

        # Evan
        [10, "Arizona", "Evan"],
        [25, "Boise State", "Evan"],
        [5, "Alabama", "Evan"],
        [160, "Maryland", "Evan"],
        [170, "Michigan State", "Evan"],
        [250, "SMU", "Evan"],
        [314, "UConn", "Evan"],

        # Jack
        [72, "Duke", "Jack"],
        [298, "Texas Tech", "Jack"],
        [359, "Xavier", "Jack"],
        [223, "Oregon", "Jack"],
        [323, "USC", "Jack"],
        [257, "San Diego State", "Jack"],
        [12, "Arkansas", "Jack"],

        # Logan
        [20, "Baylor", "Logan"],
        [61, "Creighton", "Logan"],
        [124, "Iowa", "Logan"],
        [150, "Louisville", "Logan"],
        [163, "Memphis", "Logan"],
        [170, "Michigan", "Logan"],
        [177, "Missouri", "Logan"],

        # Mike
        [52, "Clemson", "Mike"],
        [125, "Iowa State", "Mike"],
        [34, "Butler", "Mike"],
        [355, "Wisconsin", "Mike"],
        [329, "Utah State", "Mike"],
        [135, "Kentucky", "Mike"],
        [253, "Saint Mary's", "Mike"],

        # Nico
        [64, "Dayton", "Nico"],
        [200, "North Carolina", "Nico"],
        [113, "Houston", "Nico"],
        [338, "Villanova", "Nico"],
        [313, "UCLA", "Nico"],
        [16, "Auburn", "Nico"],
        [29, "Bradley", "Nico"],

        # Nick
        [333, "VCU", "Nick"],
        [185, "NC State", "Nick"],
        [18, "BYU", "Nick"],
        [279, "St. John's", "Nick"],
        [121, "Indiana", "Nick"],
        [216, "Ohio State", "Nick"],
        [336, "Vanderbilt", "Nick"],

        # Sam
        [342, "Wake Forest", "Sam"],
        [131, "Kansas", "Sam"],
        [157, "Marquette", "Sam"],
        [65, "DePaul", "Sam"],
        [236, "Purdue", "Sam"],
        [292, "Tennessee", "Sam"],
        [220, "Ole Miss", "Sam"]
    ]
    return pd.DataFrame(draft, columns=columns)

# --- FETCH DATA FROM ESPN ---
@st.cache_data(ttl=1800)
def fetch_team_schedule(team_id):
    """Fetch schedule and results for a single team from ESPN"""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{team_id}/schedule"
    r = requests.get(url)
    data = r.json()
    games = []

    for event in data.get("events", []):
        home_team = event['competitions'][0]['competitors'][0]['team']['displayName']
        away_team = event['competitions'][0]['competitors'][1]['team']['displayName']
        home_score = safe_int(event['competitions'][0]['competitors'][0].get('score'))
        away_score = safe_int(event['competitions'][0]['competitors'][1].get('score'))
        start_time = event['competitions'][0]['date']

        games.append({
            "homeTeam": home_team,
            "awayTeam": away_team,
            "homePoints": home_score,
            "awayPoints": away_score,
            "startDate": start_time
        })
    return games

@st.cache_data(ttl=1800)
def fetch_all_games(df_picks):
    """Fetch games for all teams in the draft picks"""
    all_games = []
    for _, row in df_picks.iterrows():
        team_games = fetch_team_schedule(row['team_id'])
        all_games.extend(team_games)
    return pd.DataFrame(all_games)

# --- PROCESS DATA ---
def process_data(df_picks, df_games):
    df_games['startDate'] = pd.to_datetime(df_games['startDate'])

    # Compute team records
    team_records = {}
    for _, row in df_games.iterrows():
        home, away = row['homeTeam'], row['awayTeam']
        h_pts, a_pts = row['homePoints'], row['awayPoints']

        if home not in team_records: team_records[home] = {"Wins":0, "Losses":0}
        if away not in team_records: team_records[away] = {"Wins":0, "Losses":0}

        if h_pts is not None and a_pts is not None:
            if h_pts > a_pts:
                team_records[home]['Wins'] += 1
                team_records[away]['Losses'] += 1
            elif a_pts > h_pts:
                team_records[away]['Wins'] += 1
                team_records[home]['Losses'] += 1

    df_standings = pd.DataFrame.from_dict(team_records, orient='index').reset_index()
    df_standings.rename(columns={"index": "Team"}, inplace=True)
    df_standings['Win Percentage'] = df_standings['Wins'] / (df_standings['Wins'] + df_standings['Losses'])
    df_standings['Win Percentage'] = df_standings['Win Percentage'].fillna(0)

    # Compute streaks
    df_games_sorted = df_games.sort_values(by='startDate', ascending=False)
    team_streaks = {}
    for _, row in df_games_sorted.iterrows():
        home, away = row['homeTeam'], row['awayTeam']
        h_pts, a_pts = row['homePoints'], row['awayPoints']
        if h_pts is None or a_pts is None or h_pts == a_pts: continue

        winner, loser = (home, away) if h_pts > a_pts else (away, home)
        # Update winner streak
        if winner not in team_streaks: team_streaks[winner] = 'W1'
        else:
            if team_streaks[winner].startswith('W'):
                team_streaks[winner] = f"W{int(team_streaks[winner][1:])+1}"
            else:
                team_streaks[winner] = 'W1'
        # Update loser streak
        if loser not in team_streaks: team_streaks[loser] = 'L1'
        else:
            if team_streaks[loser].startswith('L'):
                team_streaks[loser] = f"L{int(team_streaks[loser][1:])+1}"
            else:
                team_streaks[loser] = 'L1'

    df_standings['Streak'] = df_standings['Team'].map(team_streaks).fillna('N/A')

    # Merge with picks
    df_merged = pd.merge(df_picks, df_standings, left_on='team_name', right_on='Team', how='left')
    df_leaderboard = df_merged.groupby('person')['Win Percentage'].mean().reset_index()
    df_leaderboard.rename(columns={'Win Percentage':'Average Win Percentage'}, inplace=True)

    # Add Wins/Losses
    drafter_stats = df_merged.groupby('person')[['Wins','Losses']].sum().reset_index()
    df_leaderboard = pd.merge(df_leaderboard, drafter_stats, on='person', how='left')
    df_leaderboard = df_leaderboard.sort_values(by='Average Win Percentage', ascending=False).reset_index(drop=True)

    return df_leaderboard, df_merged

# --- REFRESH BUTTON ---
if st.button("Refresh Data"):
    fetch_all_games.clear()
    load_draft_picks.clear()
    st.experimental_rerun()

# --- MAIN APP ---
df_picks = load_draft_picks()
df_games = fetch_all_games(df_picks)
df_leaderboard, df_merged_picks_standings = process_data(df_picks, df_games)

# Display last updated in Central Time
central_time = datetime.now(ZoneInfo("America/Chicago"))
st.caption(f"Last updated: {central_time.strftime('%Y-%m-%d %H:%M %Z')}")

# --- LEADERBOARD ---
st.subheader("Overall Leaderboard")
st.dataframe(df_leaderboard)

# --- Individual Performance ---
st.subheader("Individual Team Performance")
for person in df_leaderboard['person']:
    with st.expander(f"{person}'s Teams"):
        df_person = df_merged_picks_standings[df_merged_picks_standings['person']==person]
        st.dataframe(df_person[['team_name','Wins','Losses','Win Percentage','Streak']])
