import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import random
import itertools
import time

# Config
SHEET_NAME = "Badminton Attendance"
WORKSHEET_NAME = "attendance"
MAX_ROUNDS = 6  # adjust for your session length

# Authenticate with Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
client = gspread.authorize(creds)

def load_players():
    ws = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    df = df[df["Status"].str.lower() == "attending"]
    return df

def generate_schedule(players, max_rounds):
    seen_pairs = set()
    seen_opponents = set()
    schedule = {}

    for round_num in range(1, max_rounds + 1):
        active = []
        for _, row in players.iterrows():
            leave_after = row["Leave_After"]
            if leave_after == "" or pd.isna(leave_after):
                active.append(row["Name"])
            else:
                try:
                    if int(leave_after) >= round_num:
                        active.append(row["Name"])
                except:
                    active.append(row["Name"])

        random.shuffle(active)
        matches = []
        used = set()

        for i in range(0, len(active), 4):
            group = active[i:i+4]
            if len(group) == 4:
                best_group = None
                best_score = 999

                for perm in itertools.permutations(group, 4):
                    team1 = tuple(sorted([perm[0], perm[1]]))
                    team2 = tuple(sorted([perm[2], perm[3]]))
                    opps = frozenset(team1 + team2)

                    score = (
                        (1 if team1 in seen_pairs else 0) +
                        (1 if team2 in seen_pairs else 0) +
                        (1 if opps in seen_opponents else 0)
                    )
                    if score < best_score:
                        best_score = score
                        best_group = perm

                team1 = tuple(sorted([best_group[0], best_group[1]]))
                team2 = tuple(sorted([best_group[2], best_group[3]]))
                opps = frozenset(team1 + team2)

                seen_pairs.add(team1)
                seen_pairs.add(team2)
                seen_opponents.add(opps)

                matches.append((team1[0], team1[1], team2[0], team2[1]))

        schedule[round_num] = matches
    return schedule

# Streamlit UI
st.set_page_config(page_title="Badminton Scheduler", page_icon="🏸", layout="wide")
st.title("🏸 Badminton Mexicano Scheduler")

auto_refresh = st.sidebar.checkbox("Auto-refresh every 30s", value=True)

players = load_players()
schedule = generate_schedule(players, MAX_ROUNDS)

st.subheader(f"Active players: {len(players)}")
st.dataframe(players[["Name", "Leave_After"]])

for rnd, matches in schedule.items():
    st.header(f"Round {rnd}")
    if not matches:
        st.write("Not enough players.")
    else:
        for idx, match in enumerate(matches, 1):
            st.write(f"Match {idx}: {match[0]} + {match[1]}  vs  {match[2]} + {match[3]}")

if auto_refresh:
    st.experimental_autorefresh(interval=30*1000)  # 30s refresh
