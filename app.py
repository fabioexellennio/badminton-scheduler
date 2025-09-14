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

# Load credentials from Streamlit Secrets
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


def generate_matchups(players, num_rounds=3, num_courts=2):
    """
    Generate rounds where EVERY player must play.
    Courts can be reused (batches) until all players are assigned.
    If players % 4 != 0, one or more get 'BYE'.
    """
    teammate_history = defaultdict(int)
    match_history = defaultdict(int)
    all_rounds = []

    for r in range(num_rounds):
        round_players = players[:]
        random.shuffle(round_players)
        matches = []

        while len(round_players) >= 4:
            best_group = None
            best_score = float("inf")

            for _ in range(30):
                if len(round_players) < 4:
                    break
                sample = random.sample(round_players, 4)
                p1, p2, p3, p4 = sample

                team1 = tuple(sorted((p1, p2)))
                team2 = tuple(sorted((p3, p4)))
                match = frozenset([team1, team2])

                score = teammate_history[team1] + teammate_history[team2] + match_history[match]

                if score < best_score:
                    best_score = score
                    best_group = sample

            if best_group:
                p1, p2, p3, p4 = best_group
                team1 = tuple(sorted((p1, p2)))
                team2 = tuple(sorted((p3, p4)))
                match = frozenset([team1, team2])

                matches.append((team1, team2))

                teammate_history[team1] += 1
                teammate_history[team2] += 1
                match_history[match] += 1

                for p in best_group:
                    round_players.remove(p)

        if round_players:
            matches.append(((tuple(round_players),), ("BYE",)))

        court = 1
        for m in matches:
            t1, t2 = m
            all_rounds.append(
                {
                    "Round": r + 1,
                    "Court": court,
                    "Team 1": " & ".join(t1) if len(t1) > 1 else t1[0],
                    "Team 2": " & ".join(t2) if len(t2) > 1 else t2[0],
                }
            )
            court += 1
            if court > num_courts:
                court = 1  # reuse courts in next batch

    return pd.DataFrame(all_rounds)


def write_matchups_to_sheet(df):
    """Write matchmaking results to a separate sheet, grouped by round."""
    sh = client.open(SHEET_NAME)
    try:
        matchup_sheet = sh.worksheet("Matchmaking")
    except gspread.WorksheetNotFound:
        matchup_sheet = sh.add_worksheet(title="Matchmaking", rows="100", cols="20")

    output_data = []
    for round_num in sorted(df["Round"].unique()):
        output_data.append([f"Round {round_num}"])
        round_data = df[df["Round"] == round_num][["Court", "Team 1", "Team 2"]]
        output_data.append(round_data.columns.tolist())
        output_data.extend(round_data.values.tolist())
        output_data.append([])

    matchup_sheet.clear()
    matchup_sheet.update(output_data)


# ======================
# Streamlit App
# ======================
st.title("🏸 Badminton Scheduler")

menu = st.sidebar.radio("Menu", ["Player List", "Matchmaking"])

if menu == "Player List":
    st.subheader("✅ Current Player List")
    df = get_players()
    st.dataframe(df)

    # ---- Add Player ----
    with st.form("add_player_form"):
        name = st.text_input("Enter player name")
        early_leave = st.checkbox("Will leave early?")
        submitted = st.form_submit_button("Add Player")

        if submitted and name:
            new_row = {"Name": name, "EarlyLeave": early_leave}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            update_players(df)
            st.success(f"{name} added successfully!")
            st.experimental_rerun()

    # ---- Delete Player ----
    if not df.empty:
        with st.form("delete_player_form"):
            key_for_selectbox = f"delete_select_{len(df)}"
            player_to_delete = st.selectbox(
                "Select player to delete",
                df["Name"].tolist(),
                key=key_for_selectbox
            )
            delete_btn = st.form_submit_button("Delete Player")

            if delete_btn:
                current_df = get_players()  # refresh before deleting
                if player_to_delete in current_df["Name"].values:
                    updated_df = current_df[current_df["Name"] != player_to_delete].reset_index(drop=True)
                    update_players(updated_df)
                    st.success(f"✅ {player_to_delete} has been removed!")
                    st.experimental_rerun()
                else:
                    st.error("⚠️ Player not found — please refresh and try again.")

elif menu == "Matchmaking":
    st.subheader("🎲 Matchmaking Generator")
    df = get_players()

    if df.empty:
        st.warning("No players yet. Please add players in 'Player List'.")
    else:
        players = df["Name"].tolist()
        num_rounds = st.number_input("Number of Rounds", 1, 20, 9)
        num_courts = st.number_input("Number of Courts", 1, 10, 3)

        if st.button("Generate Matchups"):
            matchups = generate_matchups(players, num_rounds, num_courts)
            st.dataframe(matchups)

            try:
                write_matchups_to_sheet(matchups)
                st.success("✅ Matchups have been written to the 'Matchmaking' sheet!")
            except Exception as e:
                st.error(f"❌ Failed to write to sheet: {e}")
