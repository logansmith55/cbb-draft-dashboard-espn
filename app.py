import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# --- Draft Picks ---
@st.cache_data(ttl=3600)
def load_draft_picks():
    columns = ["team_name", "person"]
    draft = [
        # Doug
        ["Saint Louis", "Doug"],
        ["Virginia", "Doug"],
        ["Cincinnati", "Doug"],
        ["Providence", "Doug"],
        ["Illinois", "Doug"],
        ["Florida", "Doug"],
        ["Gonzaga", "Doug"],

        # Evan
        ["Arizona", "Evan"],
        ["Boise State", "Evan"],
        ["Alabama", "Evan"],
        ["Maryland", "Evan"],
        ["Michigan State", "Evan"],
        ["SMU", "Evan"],
        ["UConn", "Evan"],

        # Jack
        ["Duke", "Jack"],
        ["Texas Tech", "Jack"],
        ["Xavier", "Jack"],
        ["Oregon", "Jack"],
        ["USC", "Jack"],
        ["San Diego State", "Jack"],
        ["Arkansas", "Jack"],

        # Logan
        ["Baylor", "Logan"],
        ["Creighton", "Logan"],
        ["Iowa", "Logan"],
        ["Louisville", "Logan"],
        ["Memphis", "Logan"],
        ["Michigan", "Logan"],
        ["Missouri", "Logan"],

        # Mike
        ["Clemson", "Mike"],
        ["Iowa State", "Mike"],
        ["Butler", "Mike"],
        ["Wisconsin", "Mike"],
        ["Utah State", "Mike"],
        ["Kentucky", "Mike"],
        ["Saint Mary's", "Mike"],

        # Nico
        ["Dayton", "Nico"],
        ["North Carolina", "Nico"],
        ["Houston", "Nico"],
        ["Villanova", "Nico"],
        ["UCLA", "Nico"],
        ["Auburn", "Nico"],
        ["Bradley", "Nico"],

        # Nick
        ["VCU", "Nick"],
        ["NC State", "Nick"],
        ["BYU", "Nick"],
        ["St. John's", "Nick"],
        ["Indiana", "Nick"],
        ["Ohio State", "Nick"],
        ["Vanderbilt", "Nick"],

        # Sam
        ["Wake Forest", "Sam"],
        ["Kansas", "Sam"],
        ["Marquette", "Sam"],
        ["DePaul", "Sam"],
        ["Purdue", "Sam"],
        ["Tennessee", "Sam"],
        ["Ole Miss", "Sam"]
    ]
    return pd.DataFrame(draft, columns=columns)

# --- Fetch ESPN Games ---
@st.cache_data(ttl=600)
def fetch_espn_games():
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
    response = requests.get(url)
    data = response.json()

    games = []
    for event in data.get('events', []):
        comp = event['competitions'][0]['competitors']
        home = next(c for c in comp if c['homeAway'] == 'home')
        away = next(c for c in comp if c['homeAway'] == 'away')

        games.append({
            'home_team': home['team']['displayName'],
            'away_team': away['team']['displayName'],
            'home_score': int(home['score']) if home['score'] else None,
            'away_score': int(away['score']) if away['score'] else None,
            'status': event['status']['type']['description'],
            'game_date': datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
        })

    return pd.DataFrame(games)

# --- Process Standings ---
@st.cache_data(ttl=600)
def process_data(df_picks, df_games):
    # Initialize records
    team_records = {}
    for _, row in df_games.iterrows():
        home, away, h_score, a_score = row['home_team'], row['away_team'], row['home_score'], row['away_score']
        for team in [home, away]:
            if team not in team_records:
                team_records[team] = {'Wins': 0, 'Losses': 0}

        if h_score is not None and a_score is not None:
            if h_score > a_score:
                team_records[home]['Wins'] += 1
                team_records[away]['Losses'] += 1
            elif a_score > h_score:
                team_records[away]['Wins'] += 1
                team_records[home]['Losses'] += 1

    df_standings = pd.DataFrame.from_dict(team_records, orient='index').reset_index().rename(columns={'index': 'team_name'})
    df_standings['Win Percentage'] = df_standings['Wins'] / (df_standings['Wins'] + df_standings['Losses'])

    # Calculate streaks
    df_games_sorted = df_games.sort_values(by='game_date')
    team_streaks = {}
    for _, row in df_games_sorted.iterrows():
        if row['home_score'] is None or row['away_score'] is None: continue
        winner = row['home_team'] if row['home_score'] > row['away_score'] else row['away_team']
        loser = row['away_team'] if winner == row['home_team'] else row['home_team']

        # Winner streak
        if winner not in team_streaks:
            team_streaks[winner] = 'W1'
        else:
            if team_streaks[winner].startswith('W'):
                team_streaks[winner] = f"W{int(team_streaks[winner][1:]) + 1}"
            else:
                team_streaks[winner] = 'W1'
        # Loser streak
        if loser not in team_streaks:
            team_streaks[loser] = 'L1'
        else:
            if team_streaks[loser].startswith('L'):
                team_streaks[loser] = f"L{int(team_streaks[loser][1:]) + 1}"
            else:
                team_streaks[loser] = 'L1'

    df_standings['Streak'] = df_standings['team_name'].map(team_streaks).fillna('N/A')

    # Merge picks for drafter leaderboard
    df_merged = pd.merge(df_picks, df_standings, on='team_name', how='left')
    df_leaderboard = df_merged.groupby('person')['Win Percentage'].mean().reset_index()
    df_leaderboard = df_leaderboard.rename(columns={'Win Percentage': 'Average Win Percentage'})
    df_leaderboard = df_leaderboard.sort_values('Average Win Percentage', ascending=False).reset_index(drop=True)

    return df_leaderboard, df_merged

# --- Streamlit App ---
st.title("CBB Draft Leaderboard (ESPN Data)")

# Last updated
central_time = datetime.now(ZoneInfo("America/Chicago"))
st.caption(f"Last updated: {central_time.strftime('%Y-%m-%d %H:%M %Z')}")

# Refresh button
if st.button("Refresh Data"):
    fetch_espn_games.clear()
    process_data.clear()
    st.experimental_rerun()

# Load and process
df_picks = load_draft_picks()
df_games = fetch_espn_games()
df_leaderboard, df_merged = process_data(df_picks, df_games)

# Leaderboard table
st.subheader("Overall Leaderboard")
st.dataframe(df_leaderboard)

# Individual drafter details
st.subheader("Individual Performance")
for person in df_leaderboard['person']:
    with st.expander(f"{person}'s Teams"):
        person_df = df_merged[df_merged['person'] == person][['team_name','Wins','Losses','Streak','Win Percentage']]
        avg_win_pct = person_df['Win Percentage'].mean() if not person_df.empty else 0.0
        summary = pd.DataFrame([{
            'team_name':'Total',
            'Wins': person_df['Wins'].sum(),
            'Losses': person_df['Losses'].sum(),
            'Streak':'',
            'Win Percentage': avg_win_pct
        }])
        st.dataframe(pd.concat([person_df, summary], ignore_index=True))

