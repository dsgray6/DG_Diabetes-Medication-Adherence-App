import streamlit as st
import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, time
import sqlite3
from pathlib import Path
import calendar

def create_database_connection():
    try:
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        db_path = data_dir / "diabetes_app.db"
        conn = sqlite3.connect(str(db_path))
        create_tables(conn)
        return conn
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None

def create_tables(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id TEXT PRIMARY KEY,
                  streak INTEGER DEFAULT 0)''')
                  
    conn.execute('''CREATE TABLE IF NOT EXISTS medications
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  med_name TEXT,
                  dosage REAL,
                  time_taken TIMESTAMP,
                  scheduled_time TIME,
                  date DATE)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS glucose_readings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  glucose_level REAL,
                  reading_time TIMESTAMP)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS medication_schedule
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  med_name TEXT,
                  scheduled_time TIME,
                  dosage REAL)''')

def initialize_session_state():
    if 'user_id' not in st.session_state:
        st.session_state.user_id = 'default_user'
    if 'streak' not in st.session_state:
        st.session_state.streak = 0

def get_medication_options():
    return ["Insulin", "Metformin", "Glipizide", "Januvia", "Other"]

def medication_tracker():
    st.header("Medication Tracker")
    
    current_time = datetime.now().strftime("%H:%M")
    st.subheader(f"Current Time: {current_time}")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_date = st.date_input("Select Date", datetime.now())
        
    conn = create_database_connection()
    if conn:
        display_medication_calendar(conn, st.session_state.user_id)
        
        with st.expander("Log New Medication"):
            med_name = st.selectbox("Medication Name", get_medication_options())
            if med_name == "Other":
                med_name = st.text_input("Enter medication name")
            dosage = st.number_input("Dosage", min_value=0.0)
            time_taken = st.time_input("Time Taken")
            
            if st.button("Log Medication"):
                try:
                    time_taken_str = time_taken.strftime('%H:%M:%S')
                    with conn:
                        conn.execute("""
                            INSERT INTO medications 
                            (user_id, med_name, dosage, time_taken, date)
                            VALUES (?, ?, ?, ?, ?)
                        """, (st.session_state.user_id, med_name, dosage, 
                              time_taken_str, selected_date))
                    st.success("Medication logged successfully!")
                    update_streak(conn, st.session_state.user_id)
                except Exception as e:
                    st.error(f"Error logging medication: {e}")
                finally:
                    conn.close()

def display_medication_calendar(conn, user_id):
    st.subheader("Medication Calendar")
    
    now = datetime.now()
    cal = calendar.monthcalendar(now.year, now.month)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, med_name, dosage, time_taken 
        FROM medications 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
    """, (user_id, now.strftime('%Y-%m')))
    med_data = cursor.fetchall()
    
    # Calendar display code remains the same...

def calculate_streak(conn, user_id):
    """Calculate the current streak of medication adherence"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date 
        FROM medications 
        WHERE user_id = ? 
        ORDER BY date DESC
    """, (user_id,))
    
    dates = [row[0] for row in cursor.fetchall()]
    
    if not dates:
        return 0
    
    streak = 1
    current_date = datetime.strptime(dates[0], '%Y-%m-%d').date()
    yesterday = datetime.now().date() - timedelta(days=1)
    
    # Check if the most recent medication was taken yesterday or today
    if current_date < yesterday:
        return 0
    
    # Count consecutive days
    for i in range(1, len(dates)):
        date = datetime.strptime(dates[i], '%Y-%m-%d').date()
        if (current_date - date).days == 1:
            streak += 1
            current_date = date
        else:
            break
    
    return streak

def update_streak(conn, user_id):
    """Update the user's streak in the database"""
    try:
        cursor = conn.cursor()
        streak = calculate_streak(conn, user_id)
        
        # Update or insert streak in users table
        cursor.execute("""
            INSERT OR REPLACE INTO users (user_id, streak)
            VALUES (?, ?)
        """, (user_id, streak))
        
        conn.commit()
    except Exception as e:
        st.error(f"Error updating streak: {e}")

def initialize_user(conn, user_id):
    """Initialize a new user in the database"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, streak)
            VALUES (?, 0)
        """, (user_id,))
        conn.commit()
    except Exception as e:
        st.error(f"Error initializing user: {e}")

def main():
    st.set_page_config(page_title="Diabetes Support App", layout="wide")
    initialize_session_state()
    
    # Initialize database connection
    conn = create_database_connection()
    if conn:
        initialize_user(conn, st.session_state.user_id)
    
    page = st.sidebar.selectbox(
        "Navigation",
        ["Home", "Medication Tracker", "Glucose Tracker", 
         "Community", "Resources", "Settings"]
    )
    
    if page == "Home":
        st.title("Diabetes Support App")
        if conn:
            streak = calculate_streak(conn, st.session_state.user_id)
            st.metric("Current Streak", f"{streak} days")
            display_glucose_chart()
            conn.close()
    
    elif page == "Medication Tracker":
        medication_tracker()
    
    elif page == "Glucose Tracker":
        glucose_tracker()
        
    elif page == "Community":
        st.title("Community Support")
        st.write("Connect with others in the diabetes community")
        
    elif page == "Resources":
        st.title("Resources")
        st.write("Educational materials and helpful information")
        
    elif page == "Settings":
        st.title("Settings")
        notification_time = st.time_input("Set Default Reminder Time")
        if st.button("Save Settings"):
            st.success("Settings saved successfully!")

def display_glucose_chart():
    """Display glucose readings chart"""
    conn = create_database_connection()
    if conn:
        df = pd.read_sql_query("""
            SELECT glucose_level, reading_time 
            FROM glucose_readings 
            WHERE user_id = ? 
            ORDER BY reading_time
        """, conn, params=(st.session_state.user_id,))
        
        if not df.empty:
            fig = px.line(df, x='reading_time', y='glucose_level',
                         title='Glucose Levels Over Time')
            fig.update_layout(
                xaxis_title="Time",
                yaxis_title="Glucose Level",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No glucose readings available yet.")
        conn.close()

def glucose_tracker():
    """Handle glucose tracking functionality"""
    st.subheader("Glucose Tracker")
    
    glucose_level = st.number_input("Glucose Level (mg/dL)", 
                                  min_value=0, max_value=600)
    
    if st.button("Log Glucose Reading"):
        conn = create_database_connection()
        if conn:
            try:
                with conn:
                    conn.execute("""
                        INSERT INTO glucose_readings 
                        (user_id, glucose_level, reading_time)
                        VALUES (?, ?, ?)
                    """, (st.session_state.user_id, glucose_level, 
                          datetime.now()))
                st.success("Glucose level logged successfully!")
            except Exception as e:
                st.error(f"Error logging glucose level: {e}")
            finally:
                conn.close()

if __name__ == "__main__":
    main()