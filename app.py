import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- Draft picks mapping ---
@st.cache_data(ttl=3600)
def load_draft_picks():
    # ESPN team IDs (you have to map them to your draft schools)
    # Example ESPN IDs; you should adjust if needed
    draft = [
        # Doug
        ["Saint Louis", 276, "Doug"],
        ["Virginia", 258, "Doug"],
        ["Cincinnati", 201, "Doug"],
        ["Providence", 259, "Doug"],
        ["Illinois", 229, "Doug"],
        ["Florida", 110, "Doug"],
        ["Gonzaga", 225, "Doug"],

        # Evan
        ["Arizona", 12, "Evan"],
        ["Boise State", 38, "Evan"],
        ["Alabama", 333, "Evan"],
        ["Maryland", 120, "Evan"],
        ["Michigan State", 127, "Evan"],
        ["SMU", 254, "Evan"],
        ["UConn", 41, "Evan"],

        # Jack
        ["Duke", 150, "Jack"],
        ["Texas Tech", 264, "Jack"],
        ["Xavier", 274, "Jack"],
        ["Oregon", 248, "Jack"],
        ["USC", 30, "Jack"],
        ["San Diego State", 21, "Jack"],
        ["Arkansas", 8, "Jack"],

        # Logan
        ["Baylor", 239, "Logan"],
        ["Creighton", 264, "Logan"],
        ["Iowa", 221, "Logan"],
        ["Louisville", 97, "Logan"],
        ["Memphis", 235, "Logan"],
        ["Michigan", 130, "Logan"],
        ["Missouri", 142, "Logan"],

        # Mike
        ["Clemson", 206, "Mike"],
        ["Iowa State", 66, "Mike"],
        ["Butler", 264, "Mike"],
        ["Wisconsin", 275, "Mike"],
        ["Utah State", 328, "Mike"],
        ["Kentucky", 96, "Mike"],
        ["Saint Mary's", 305, "Mike"],

        # Nico
        ["Dayton", 66, "Nico"],
        ["North Carolina", 153, "Nico"],
        ["Houston", 65, "Nico"],
        ["Villanova", 222, "Nico"],
        ["UCLA", 26, "Nico"],
        ["Auburn", 2, "Nico"],
        ["Bradley", 60, "Nico"],

        # Nick
        ["VCU", 270, "Nick"],
        ["NC State", 152, "Nick"],
        ["BYU", 56, "Nick"],
        ["St. John's", 277, "Nick"],
        ["Indiana", 84, "Nick"],
        ["Ohio State", 161, "Nick"],
        ["Vanderbilt", 238, "Nick"],

        # Sam
        ["Wake Forest", 276, "Sam"],
        ["Kansas", 230, "Sam"],
        ["Marquette", 143, "Sam"],
        ["DePaul", 60, "Sam"],
        ["Purdue", 176, "Sam"],
        ["Tennessee", 263, "Sam"],
        ["Ole Miss", 145, "Sam"],
    ]
    return pd.DataFrame(draft, columns=["team_name", "espn_id", "person"])


# --- Fetch full season schedule for a team ---
def fetch_team_schedule(team_id):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{team_id}/schedule"
    r = requests.get(url)
    if r.status_code != 200:
        return pd.DataFrame()
    data = r.json()
    games = []
    for event in data.get("events", []):
        competitions = event.get("competitions", [])
        if not competitions:
            continue
        comp = competitions[0]
        home_team = comp['competitors'][0]['team']['displayName']
        away_team = comp['competitors'][1]['team']['displayName']
        home_score = comp['competitors'][0].get('score')
        away_score = comp['competitors'][1].get('score')
        game_date = comp.get('date')
        games.append({
            "game_date": pd.to_datetime(game_date),
            "home_team": home_team,
            "away_team": away_team,
            "home_points": int(home_score) if home_score is not None else None,
            "away_points": int(away_score) if away_score is not None else None
        })
    return pd.DataFrame(games)


# --- Fetch all games for draft teams ---
@st.cache_data(ttl=3600)
def fetch_all_games(df_picks):
    all_games = []
    for _, row in df_picks.iterrows():
        team_id = row['espn_id']
        team_games = fetch_team_schedule(team_id)
        if not team_games.empty:
            all_games.append(team_games)
    if all_games:
        return pd.concat(all_games).drop_duplicates().reset_index(drop=True)
    return pd.DataFrame()


# --- Process leaderboard ---
@st.cache_data(ttl=3600)
def process_leaderboard(df_picks, df_games):
    # Calculate Wins/Losses per team
    team_records = {}
    for _, row in df_games.iterrows():
        for team, pts, opp, opp_pts in [(row['home_team'], row['home_points'], row['away_team'], row['away_points']),
                                        (row['away_team'], row['away_points'], row['home_team'], row['home_points'])]:
            if team not in team_records:
                team_records[team] = {"Wins": 0, "Losses": 0}
            if pts is not None and opp_pts is not None:
                if pts > opp_pts:
                    team_records[team]['Wins'] += 1
                elif pts < opp_pts:
                    team_records[team]['Losses'] += 1

    df_standings = pd.DataFrame.from_dict(team_records, orient='index').reset_index()
    df_standings.rename(columns={"index": "team_name"}, inplace=True)
    df_standings['Win Percentage'] = df_standings['Wins'] / (df_standings['Wins'] + df_standings['Losses'])

    # Merge with draft picks
    df_merged = pd.merge(df_picks, df_standings, on="team_name", how="left")

    # Leaderboard per drafter
    df_leaderboard = df_merged.groupby("person")[["Wins", "Losses", "Win Percentage"]].mean().reset_index()
    df_leaderboard = df_leaderboard.sort_values(by="Win Percentage", ascending=False)
    return df_leaderboard, df_merged


# --- Streamlit App ---
st.title("Metro Sharon CBB Draft Leaderboard")

df_picks = load_draft_picks()
df_games = fetch_all_games(df_picks)
df_leaderboard, df_merged = process_leaderboard(df_picks, df_games)

# Last updated in Central Time
central_time = datetime.now(ZoneInfo("America/Chicago"))
st.caption(f"Last updated: {central_time.strftime('%Y-%m-%d %H:%M %Z')}")

# --- Leaderboard ---
st.subheader("Overall Leaderboard")
st.dataframe(df_leaderboard)

# --- Individual Performance ---
st.subheader("Individual Team Performance")
for person in df_picks['person'].unique():
    with st.expander(f"{person}'s Teams"):
        df_person = df_merged[df_merged['person'] == person][["team_name", "Wins", "Losses", "Win Percentage"]]
        summary = pd.DataFrame([{
            "team_name": "Total",
            "Wins": df_person["Wins"].sum(),
            "Losses": df_person["Losses"].sum(),
            "Win Percentage": df_person["Win Percentage"].mean()
        }])
        st.dataframe(pd.concat([df_person, summary], ignore_index=True))
