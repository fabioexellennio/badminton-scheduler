import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from collections import defaultdict
import random

# ======================
# Google Sheets Setup
# ======================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Load credentials from Streamlit Secrets (not from file)
creds_dict = st.secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(dict(creds_dict), scopes=scope)
client = gspread.authorize(creds)

# Replace with your Google Sheet name
SHEET_NAME = "badminton_scheduler"
sheet = client.open(SHEET_NAME).sheet1


# ======================
# Functions
# ======================
def get_players():
    """Fetch player list from Google Sheet"""
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df


def update_players(df):
    """Update player list in Google Sheet"""
    sheet.clear()
    df = df.fillna("")
    sheet.update([df.columns.values.tolist()] + df.values.tolist())


def generate_matchups(players, num_rounds=9):
    """
    Generate multiple rounds of randomized doubles matchups
    with minimal repeats (teammates or opponents).
    Default = 9 rounds (~3 hours if 20min/game).
    """

    teammate_history = defaultdict(int)  # (p1, p2) -> count
    opponent_history = defaultdict(int)  # (p1, p2) -> count

    all_rounds = []

    for r in range(num_rounds):
        round_players = players[:]  # copy
        random.shuffle(round_players)
        round_courts = []

        while len(round_players) >= 4:
            # Choose best group of 4 minimizing repeats
            best_group = None
            best_score = float("inf")

            for _ in range(20):  # try 20 random groups
                sample = random.sample(round_players, 4)
                p1, p2, p3, p4 = sample

                # Calculate repeat score
                score = (
                    teammate_history[tuple(sorted((p1, p2)))]
                    + teammate_history[tuple(sorted((p3, p4)))]
                    + opponent_history[tuple(sorted((p1, p3)))]
                    + opponent_history[tuple(sorted((p1, p4)))]
                    + opponent_history[tuple(sorted((p2, p3)))]
                    + opponent_history[tuple(sorted((p2, p4)))]
                )

                if score < best_score:
                    best_score = score
                    best_group = sample

            # Assign chosen group
            p1, p2, p3, p4 = best_group
            round_courts.append(
                {
                    "Round": r + 1,
                    "Court": len(round_courts) + 1,
                    "Team 1": f"{p1} & {p2}",
                    "Team 2": f"{p3} & {p4}",
                }
            )

            # Update history
            teammate_history[tuple(sorted((p1, p2)))] += 1
            teammate_history[tuple(sorted((p3, p4)))] += 1

            for a, b in [(p1, p3), (p1, p4), (p2, p3), (p2, p4)]:
                opponent_history[tuple(sorted((a, b)))] += 1

            # Remove from pool
            for p in [p1, p2, p3, p4]:
                round_players.remove(p)

        all_rounds.extend(round_courts)

    return pd.DataFrame(all_rounds)


# ======================
# Streamlit App
# ======================
st.title("🏸 Badminton Scheduler")

menu = st.sidebar.radio("Menu", ["Player List", "Matchmaking"])

if menu == "Player List":
    st.subheader("✅ Current Player List")
    df = get_players()
    st.dataframe(df)

    with st.form("add_player_form"):
        name = st.text_input("Enter player name")
        early_leave = st.checkbox("Will leave early?")
        submitted = st.form_submit_button("Add Player")

        if submitted and name:
            new_row = {"Name": name, "EarlyLeave": early_leave}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            update_players(df)
            st.success(f"{name} added successfully!")

elif menu == "Matchmaking":
    st.subheader("🎲 Matchmaking Generator")
    df = get_players()

    if df.empty:
        st.warning("No players yet. Please add players in 'Player List'.")
    else:
        players = df["Name"].tolist()
        matchups = generate_matchups(players, num_rounds=9)  # 9 rounds ≈ 3 hours
        st.dataframe(matchups)