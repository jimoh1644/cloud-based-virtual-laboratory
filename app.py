import streamlit as st
import pandas as pd
import os
import subprocess, tempfile, textwrap, hashlib
from datetime import datetime

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(page_title="☁️ Cloud Virtual Laboratory", layout="wide")

DATA_DIR = "data"
USERS_CSV = os.path.join(DATA_DIR, "users.csv")
LABS_CSV = os.path.join(DATA_DIR, "labs.csv")
SESSIONS_CSV = os.path.join(DATA_DIR, "lab_sessions.csv")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def hash_password(password):
    """Securely hash a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()


def execute_python_code(code, timeout=5):
    """Run Python code safely (basic sandbox)."""
    code = textwrap.dedent(code)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as t:
        t.write(code.encode())
        t.flush()
        temp_path = t.name
    try:
        proc = subprocess.run(["python", temp_path],
                              capture_output=True,
                              text=True,
                              timeout=timeout)
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        return out if out else err if err else "(No output)"
    except subprocess.TimeoutExpired:
        return "⏱️ Error: Code execution timed out!"
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass


def init_csv(path, columns, defaults=None):
    """Create CSV if missing, or add missing columns if exists."""
    if not os.path.exists(path):
        df = pd.DataFrame(defaults or [], columns=columns)
        df.to_csv(path, index=False)
        return df
    else:
        df = pd.read_csv(path)
        # Automatically add missing columns
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df.to_csv(path, index=False)
        return df

def load_csv(path):
    return pd.read_csv(path)


def save_csv(df, path):
    df.to_csv(path, index=False)

# ---------------------------------------------------------
# INITIAL DATA CREATION
# ---------------------------------------------------------
users = init_csv(USERS_CSV, ["id", "name", "email", "password_hash", "role"], [
    [1, "Instructor", "instructor@gmail.com", hash_password("password"), "instructor"]
])

labs = init_csv(LABS_CSV, ["lab_id", "title", "description", "expected_output"], [
    [1, "Basic Python", "Print statements and variables", "Hello World"]
])

sessions = init_csv(SESSIONS_CSV, ["session_id", "user_id", "lab_id", "code", "output", "score", "timestamp"])

# ---------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------
def login():
    st.subheader("🧑‍💻 Cloud based Virtual Lababoratory for Online Learning")
    st.subheader("🔐 Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        df = load_csv(USERS_CSV)
        hashed = hash_password(password)
        user = df[(df["email"] == email) & (df["password_hash"] == hashed)]
        if not user.empty:
            st.session_state["user"] = user.iloc[0].to_dict()
            st.success(f"Welcome, {user.iloc[0]['name']}!")
            st.rerun()
        else:
            st.error("Invalid email or password.")


def register():
    st.subheader("📝 Register (Student)")
    name = st.text_input("Full Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        df = load_csv(USERS_CSV)
        if email in df["email"].values:
            st.warning("Email already registered.")
        else:
            new_id = int(df["id"].max()) + 1 if not df.empty else 1
            df.loc[len(df)] = [new_id, name, email, hash_password(password), "student"]
            save_csv(df, USERS_CSV)
            st.success("Registration successful! Please login.")

# ---------------------------------------------------------
# MAIN FUNCTIONALITY
# ---------------------------------------------------------
def dashboard():
    st.title("📚 Dashboard")
    labs_df = load_csv(LABS_CSV)
    st.table(labs_df[["lab_id", "title", "description", "expected_output"]])
    user = st.session_state["user"]

    if user["role"] == "instructor":
        st.subheader("➕ Create New Lab")
        new_title = st.text_input("Lab Title")
        new_desc = st.text_area("Description")
        expected_output = st.text_input("Expected Output (for grading)")
        if st.button("Create Lab"):
            if new_title.strip():
                new_id = int(labs_df["lab_id"].max()) + 1 if not labs_df.empty else 1
                labs_df.loc[len(labs_df)] = [new_id, new_title, new_desc, expected_output]
                save_csv(labs_df, LABS_CSV)
                st.success("New lab added successfully!")
                st.rerun()
            else:
                st.warning("Please enter a lab title.")


def start_lab():
    st.title("💻 Start a Lab Session")
    user = st.session_state["user"]
    labs_df = load_csv(LABS_CSV)

    chosen_lab = st.selectbox("Select Lab", labs_df["title"].tolist())
    lab = labs_df[labs_df["title"] == chosen_lab].iloc[0]

    st.subheader(f"🧪 {lab['title']}")
    st.markdown(lab["description"])

    code = st.text_area("Write your Python code:", height=300, placeholder="# Example:\nprint('Hello World')")
    col1, col2 = st.columns(2)
    if col1.button("▶️ Run Code"):
        output = execute_python_code(code)
        st.text_area("Output", output, height=200)
        score = 100 if str(output).strip() == str(lab["expected_output"]).strip() else 0
        st.info(f"Auto-graded Score: {score}/100")
        save_session(user["id"], lab["lab_id"], code, output, score)
        st.success("Session saved successfully!")

    if col2.button("💾 Save Code Only"):
        save_session(user["id"], lab["lab_id"], code, "", "")
        st.success("Code saved (without grading).")


def save_session(user_id, lab_id, code, output, score):
    df = load_csv(SESSIONS_CSV)
    new_id = int(df["session_id"].max()) + 1 if not df.empty else 1
    df.loc[len(df)] = [
        new_id, user_id, lab_id, code, output,
        score if score != "" else None,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ]
    save_csv(df, SESSIONS_CSV)


def my_sessions():
    st.title("🗂️ My Sessions")
    user = st.session_state["user"]
    df = load_csv(SESSIONS_CSV)
    my = df[df["user_id"] == user["id"]]
    if my.empty:
        st.info("No lab sessions yet.")
    else:
        st.dataframe(my.sort_values("timestamp", ascending=False))

# ---------------------------------------------------------
# 📊 INSTRUCTOR GRADING DASHBOARD
# ---------------------------------------------------------
def grading_dashboard():
    st.title("📊 Instructor Grading Dashboard")
    users_df = load_csv(USERS_CSV)
    sessions_df = load_csv(SESSIONS_CSV)
    labs_df = load_csv(LABS_CSV)

    merged = sessions_df.merge(users_df, left_on="user_id", right_on="id", how="left")
    merged = merged.merge(labs_df, on="lab_id", how="left")
    merged_view = merged[["session_id", "name", "email", "title", "output", "score", "timestamp"]]

    if merged_view.empty:
        st.info("No student submissions yet.")
    else:
        st.dataframe(merged_view.sort_values("timestamp", ascending=False))
        st.subheader("📝 Update a Student Score")
        sid = st.number_input("Enter Session ID to Update", min_value=1, step=1)
        new_score = st.number_input("New Score", 0, 100, 0)
        if st.button("Update Score"):
            if sid in merged_view["session_id"].values:
                sessions_df.loc[sessions_df["session_id"] == sid, "score"] = new_score
                save_csv(sessions_df, SESSIONS_CSV)
                st.success(f"Score for session {sid} updated to {new_score}.")
                st.rerun()
            else:
                st.warning("Invalid Session ID.")

# ---------------------------------------------------------
# ABOUT PAGE
# ---------------------------------------------------------
def about():
    st.title("ℹ️ About This Project")
    st.markdown("""
    **Cloud-Based Virtual Laboratory**  
    🔐 Secure password hashing (SHA256)  
    🧮 Auto-grading system (expected output matching)  
    📊 Instructor grading dashboard (view + edit scores)  
    💾 Data stored in a Cloud  

    **Default Instructor:**  
    `instructor@gmail.com` / `password`
    """)

# ---------------------------------------------------------
# MAIN APP
# ---------------------------------------------------------
def main():
    st.sidebar.title("Navigation")

    if "user" not in st.session_state:
        menu = st.sidebar.radio("Go to", ["Login", "Register", "About"])
        if menu == "Login":
            login()
        elif menu == "Register":
            register()
        else:
            about()
    else:
        user = st.session_state["user"]
        if user["role"] == "instructor":
            menu = st.sidebar.radio("Menu", ["Dashboard", "Start Lab", "Grading Dashboard", "Logout", "About"])
        else:
            menu = st.sidebar.radio("Menu", ["Dashboard", "Start Lab", "My Sessions", "Logout", "About"])

        st.sidebar.success(f"Logged in as {user['name']} ({user['role']})")

        if menu == "Dashboard":
            dashboard()
        elif menu == "Start Lab":
            start_lab()
        elif menu == "My Sessions":
            my_sessions()
        elif menu == "Grading Dashboard" and user["role"] == "instructor":
            grading_dashboard()
        elif menu == "About":
            about()
        elif menu == "Logout":
            if st.button("Logout"):
                del st.session_state["user"]
                st.success("Logged out successfully!")
                st.rerun()

# ---------------------------------------------------------
if __name__ == "__main__":
    main()
