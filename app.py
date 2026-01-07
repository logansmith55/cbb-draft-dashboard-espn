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
        ["Saint Louis", "Doug"], ["Virginia", "Doug"], ["Cincinnati", "Doug"],
        ["Providence", "Doug"], ["Illinois", "Doug"], ["Florida", "Doug"], ["Gonzaga", "Doug"],
        # Evan
        ["Arizona", "Evan"], ["Boise State", "Evan"], ["Alabama", "Evan"],
        ["Maryland", "Evan"], ["Michigan State", "Evan"], ["SMU", "Evan"], ["UConn", "Evan"],
        # Jack
        ["Duke", "Jack"], ["Texas Tech", "Jack"], ["Xavier", "Jack"],
        ["Oregon", "Jack"], ["USC", "Jack"], ["San Diego State", "Jack"], ["Arkansas", "Jack"],
        # Logan
        ["Baylor", "Logan"], ["Creighton", "Logan"], ["Iowa", "Logan"],
        ["Louisville", "Logan"], ["Memphis", "Logan"], ["Michigan", "Logan"], ["Missouri", "Logan"],
        # Mike
        ["Clemson", "Mike"], ["Iowa State", "Mike"], ["Butler", "Mike"],
        ["Wisconsin", "Mike"], ["Utah State", "Mike"], ["Kentucky", "Mike"], ["Saint Mary's", "Mike"],
        # Nico
        ["Dayton", "Nico"], ["North Carolina", "Nico"], ["Houston", "Nico"],
        ["Villanova", "Nico"], ["UCLA", "Nico"], ["Auburn", "Nico"], ["Bradley", "Nico"],
        # Nick
        ["VCU", "Nick"], ["NC State", "Nick"], ["BYU", "Nick"],
        ["St. John's", "Nick"], ["Indiana", "Nick"], ["Ohio State", "Nick"], ["Vanderbilt", "Nick"],
        # Sam
        ["Wake Forest", "Sam"], ["Kansas", "Sam"], ["Marquette", "Sam"],
        ["DePaul", "Sam"], ["Purdue", "Sam"], ["Tennessee", "Sam"], ["Ole Miss", "Sam"]
    ]
    return pd.DataFrame(draft, columns=columns)

# --- Scrape ESPN games ---
@st.cache_data(ttl=3600)
def fetch_espn_data():
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
    resp = requests.get(url)
    data = resp.json()

    games_list = []
    teams_set = set()

    for event in data.get("events", []):
        home = event["competitions"][0]["competitors"][0]
        away = event["competitions"][0]["competitors"][1]

        home_team = home["team"]["displayName"]
        away_team = away["team"]["displayName"]

        home_score = int(home["score"]) if home["score"] else None
        away_score = int(away["score"]) if away["score"] else None

        game_date = event["date"]

        games_list.append({
            "homeTeam": home_team,
            "awayTeam": away_team,
            "homePoints": home_score,
            "awayPoints": away_score,
            "startDate": pd.to_datetime(game_date)
        })

        teams_set.update([home_team, away_team])

    df_games = pd.DataFrame(games_list)
    df_teams = pd.DataFrame([{"team_name": t} for t in teams_set])
    return df_teams, df_games

# --- Process data ---
@st.cache_data(ttl=3600)
def process_data(df_picks, df_teams, df_games):
    # Compute records
    team_records = {}
    for _, row in df_games.iterrows():
        h, a = row['homeTeam'], row['awayTeam']
        hp, ap = row['homePoints'], row['awayPoints']

        for t in [h, a]:
            if t not in team_records:
                team_records[t] = {'Wins': 0, 'Losses': 0}

        if hp is not None and ap is not None:
            if hp > ap:
                team_records[h]['Wins'] += 1
                team_records[a]['Losses'] += 1
            elif ap > hp:
                team_records[a]['Wins'] += 1
                team_records[h]['Losses'] += 1

    df_standings = pd.DataFrame.from_dict(team_records, orient='index').reset_index()
    df_standings.rename(columns={'index': 'Team'}, inplace=True)
    df_standings['Win Percentage'] = df_standings['Wins'] / (df_standings['Wins'] + df_standings['Losses'])

    # Streaks
    df_games_sorted = df_games.sort_values(by='startDate', ascending=False)
    team_streaks = {}
    for _, row in df_games_sorted.iterrows():
        h, a = row['homeTeam'], row['awayTeam']
        hp, ap = row['homePoints'], row['awayPoints']
        if hp is None or ap is None:
            continue

        if hp > ap:
            winner, loser = h, a
        else:
            winner, loser = a, h

        # Update streak
        if winner not in team_streaks:
            team_streaks[winner] = "W1"
        else:
            if team_streaks[winner].startswith("W"):
                team_streaks[winner] = f"W{int(team_streaks[winner][1:])+1}"
            else:
                team_streaks[winner] = "W1"

        if loser not in team_streaks:
            team_streaks[loser] = "L1"
        else:
            if team_streaks[loser].startswith("L"):
                team_streaks[loser] = f"L{int(team_streaks[loser][1:])+1}"
            else:
                team_streaks[loser] = "L1"

    df_standings['Streak'] = df_standings['Team'].map(team_streaks).fillna('N/A')

    # Next game
    now = pd.Timestamp.now(tz='America/Chicago')
    df_future = df_games[df_games['startDate'] > now]
    next_game_info = {}
    for team in df_standings['Team']:
        team_future = df_future[(df_future['homeTeam']==team) | (df_future['awayTeam']==team)]
        if not team_future.empty:
            g = team_future.sort_values('startDate').iloc[0]
            opponent = g['awayTeam'] if g['homeTeam']==team else g['homeTeam']
            next_game_info[team] = {'opponent': opponent, 'date': g['startDate'].strftime('%Y-%m-%d %H:%M')}

    df_standings['Next Game Opponent'] = df_standings['Team'].map(lambda x: next_game_info.get(x, {}).get('opponent', 'N/A'))
    df_standings['Next Game Date'] = df_standings['Team'].map(lambda x: next_game_info.get(x, {}).get('date', 'N/A'))

    # Merge with picks for leaderboard
    df_merged = pd.merge(df_picks, df_standings, left_on='team_name', right_on='Team', how='left')
    df_leaderboard = df_merged.groupby('person')['Win Percentage'].mean().reset_index()
    df_leaderboard.rename(columns={'Win Percentage':'Average Win Percentage'}, inplace=True)

    stats = df_merged.groupby('person')[['Wins','Losses']].sum().reset_index()
    stats['Total Games Played'] = stats['Wins'] + stats['Losses']
    df_leaderboard = pd.merge(df_leaderboard, stats, on='person', how='left')

    return df_leaderboard, df_merged

# --- Streamlit App ---
st.title("Metro Sharon CBB Draft Leaderboard")

# Last updated in Central Time
st.caption(f"Last updated: {datetime.now(ZoneInfo('America/Chicago')).strftime('%Y-%m-%d %H:%M %Z')}")

# Load draft picks
df_picks = load_draft_picks()

# Fetch ESPN data
df_teams, df_games = fetch_espn_data()

# Process data
df_leaderboard, df_merged = process_data(df_picks, df_teams, df_games)

# Filter
selected_persons = st.multiselect("Filter by Person", options=df_leaderboard['person'].unique(), default=df_leaderboard['person'].unique())
filtered_leaderboard = df_leaderboard[df_leaderboard['person'].isin(selected_persons)]

# Show leaderboard
st.subheader("Overall Leaderboard")
st.dataframe(filtered_leaderboard)

# Individual drafter details
st.subheader("Individual Performance")
for person in df_leaderboard['person'].unique():
    with st.expander(f"{person}'s Teams"):
        df_person = df_merged[df_merged['person']==person][['team_name','Wins','Losses','Streak','Win Percentage']]
        avg_win = df_person['Win Percentage'].mean() if not df_person.empty else 0
        summary = pd.DataFrame([{'team_name':'Total','Wins':df_person['Wins'].sum(),'Losses':df_person['Losses'].sum(),'Streak':'','Win Percentage':avg_win}])
        final_df = pd.concat([df_person, summary], ignore_index=True)
        st.dataframe(final_df)
