import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

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
    sheet.update([df.columns.values.tolist()] + df.values.tolist())


def generate_matchups(players):
    """Generate randomized doubles matchups with minimal repeats"""
    import random

    random.shuffle(players)
    courts = []

    for i in range(0, len(players), 4):
        if i + 3 < len(players):
            p1, p2, p3, p4 = players[i : i + 4]
            courts.append(
                {
                    "Court": len(courts) + 1,
                    "Team 1": f"{p1} & {p2}",
                    "Team 2": f"{p3} & {p4}",
                }
            )
    return pd.DataFrame(courts)


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
            df = df.append(new_row, ignore_index=True)
            update_players(df)
            st.success(f"{name} added successfully!")

elif menu == "Matchmaking":
    st.subheader("🎲 Matchmaking Generator")
    df = get_players()

    if df.empty:
        st.warning("No players yet. Please add players in 'Player List'.")
    else:
        players = df["Name"].tolist()
        matchups = generate_matchups(players)
        st.dataframe(matchups)