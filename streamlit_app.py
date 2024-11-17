import streamlit as st
from datetime import datetime, timedelta, time
import pandas as pd
import plotly.express as px
import sqlite3
from pathlib import Path
import calendar

# Database Functions
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

def calculate_streak(conn, user_id):
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
    
    if current_date < yesterday:
        return 0
    
    for i in range(1, len(dates)):
        date = datetime.strptime(dates[i], '%Y-%m-%d').date()
        if (current_date - date).days == 1:
            streak += 1
            current_date = date
        else:
            break
    
    return streak

# Component Functions
def medication_tracker():
    st.header("Medication Tracker")
    
    current_time = datetime.now().strftime("%H:%M")
    st.subheader(f"Current Time: {current_time}")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_date = st.date_input("Select Date", datetime.now())
    
    med_options = ["Insulin", "Metformin", "Glipizide", "Januvia", "Other"]
    
    # Remove the expander here and just show the form directly
    st.subheader("Log New Medication")
    med_name = st.selectbox("Medication Name", med_options)
    if med_name == "Other":
        med_name = st.text_input("Enter medication name")
    dosage = st.number_input("Dosage", min_value=0.0)
    time_taken = st.time_input("Time Taken")
    
    if st.button("Log Medication"):
        conn = create_database_connection()
        if conn:
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
            except Exception as e:
                st.error(f"Error logging medication: {e}")
            finally:
                conn.close()

def display_glucose_chart():
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
    st.subheader("Glucose Tracker")
    
    glucose_level = st.number_input("Glucose Level (mg/dL)", 
                                  min_value=0, max_value=600)
    
    if st.button("Log Glucose Reading", key="log_glucose_button"):
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

def display_medication_calendar():
    st.subheader("Medication Calendar")
    
    now = datetime.now()
    cal = calendar.monthcalendar(now.year, now.month)
    
    conn = create_database_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, med_name, dosage, time_taken 
            FROM medications 
            WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        """, (st.session_state.user_id, now.strftime('%Y-%m')))
        med_data = cursor.fetchall()
        
        # Display calendar
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        cols = st.columns(7)
        
        for idx, day in enumerate(days):
            cols[idx].write(day)
        
        for week in cal:
            cols = st.columns(7)
            for idx, day in enumerate(week):
                if day != 0:
                    date_str = f"{now.year}-{now.month:02d}-{day:02d}"
                    day_meds = [m for m in med_data if m[0] == date_str]
                    
                    if day_meds:
                        cols[idx].markdown(f"**{day}** ✅")
                    else:
                        cols[idx].write(day)
        
        conn.close()

def initialize_session_state():
    if 'user_id' not in st.session_state:
        st.session_state.user_id = 'default_user'
    if 'page' not in st.session_state:
        st.session_state.page = 'Home'

def main():
    st.set_page_config(
        page_title="Diabetes Support App",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    initialize_session_state()
    
    # Sidebar Navigation
    with st.sidebar:
        st.title("Navigation")
        pages = {
            "Home": "🏠",
            "Medication Tracker": "💊",
            "Glucose Tracker": "📊",
            "Community": "👥",
            "Resources": "📚",
            "Settings": "⚙️"
        }
        
        for page, icon in pages.items():
            if st.button(f"{icon} {page}", key=f"nav_{page}"):  # Added unique key
                st.session_state.page = page

    # Main Content
    if st.session_state.page == "Home":
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Timer and Medication Status
            current_time = datetime.now().strftime("%H:%M")
            st.header(f"🕐 {current_time}")
            
            if st.button("Mark as taken"):
                st.success("Medication marked as taken!")
                conn = create_database_connection()
                if conn:
                    try:
                        with conn:
                            conn.execute("""
                                INSERT INTO medications 
                                (user_id, med_name, time_taken, date)
                                VALUES (?, 'Daily Medication', ?, ?)
                            """, (st.session_state.user_id, datetime.now(), 
                                  datetime.now().date()))
                    finally:
                        conn.close()
            
            # Streak Display
            conn = create_database_connection()
            if conn:
                streak = calculate_streak(conn, st.session_state.user_id)
                st.metric("Current Streak", f"{streak} days", "Keep it up! 🎯")
                conn.close()
            
            # Calendar View
            display_medication_calendar()
            
            # Medication Input - Now directly showing the form instead of using an expander
            st.subheader("Log Medication")
            med_options = ["Insulin", "Metformin", "Glipizide", "Januvia", "Other"]
            med_name = st.selectbox("Medication Name", med_options, key="home_med_name")
            if med_name == "Other":
                med_name = st.text_input("Enter medication name", key="home_med_other")
            dosage = st.number_input("Dosage", min_value=0.0, key="home_dosage")
            time_taken = st.time_input("Time Taken", key="home_time")
            
            if st.button("Log Medication", key="log_med_button"):
                conn = create_database_connection()
                if conn:
                    try:
                        time_taken_str = time_taken.strftime('%H:%M:%S')
                        with conn:
                            conn.execute("""
                                INSERT INTO medications 
                                (user_id, med_name, dosage, time_taken, date)
                                VALUES (?, ?, ?, ?, ?)
                            """, (st.session_state.user_id, med_name, dosage, 
                                  time_taken_str, datetime.now().date()))
                        st.success("Medication logged successfully!")
                    except Exception as e:
                        st.error(f"Error logging medication: {e}")
                    finally:
                        conn.close()
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Timer and Medication Status
            current_time = datetime.now().strftime("%H:%M")
            st.header(f"🕐 {current_time}")
            
            if st.button("Mark as taken", key="mark_taken_button"):
                st.success("Medication marked as taken!")
                conn = create_database_connection()
                if conn:
                    try:
                        with conn:
                            conn.execute("""
                                INSERT INTO medications 
                                (user_id, med_name, time_taken, date)
                                VALUES (?, 'Daily Medication', ?, ?)
                            """, (st.session_state.user_id, datetime.now(), 
                                  datetime.now().date()))
                    finally:
                        conn.close()
            
            # Streak Display
            conn = create_database_connection()
            if conn:
                streak = calculate_streak(conn, st.session_state.user_id)
                st.metric("Current Streak", f"{streak} days", "Keep it up! 🎯")
                conn.close()
            
            # Calendar View
            display_medication_calendar()
            
            # Medication Input
            with st.expander("Log Medication"):
                medication_tracker()
        
        with col2:
            st.header("Awareness and Education")
            
            # Glucose Chart
            display_glucose_chart()
            
            # Educational Sections
            with st.expander("📋 FAQ's"):
                st.write("""
                ### Frequently Asked Questions
                
                **Q: How often should I check my glucose?**
                - Before meals and at bedtime
                - When you feel symptoms of low or high blood sugar
                - Before and after exercise
                
                **Q: What are normal blood sugar levels?**
                - Before meals: 80-130 mg/dL
                - 2 hours after meals: Less than 180 mg/dL
                
                **Q: When should I take my medication?**
                - Follow your healthcare provider's specific instructions
                - Try to take medications at the same time each day
                - Some medications need to be taken with food
                
                **Q: What should I do if I miss a dose?**
                - Contact your healthcare provider for guidance
                - Never double up on doses without medical advice
                - Record any missed doses in the app
                """)
            
            with st.expander("📚 Education"):
                st.write("""
                ### Educational Resources
                
                **Medication Information:**
                - [Understanding Your Diabetes Medications](link)
                - [Proper Injection Techniques](link)
                - [Storage Guidelines](link)
                
                **Video Tutorials:**
                - How to Check Blood Sugar
                - Proper Insulin Injection
                - Using Your Glucose Meter
                
                **Downloads:**
                - Medication Schedule Template
                - Blood Sugar Log Sheet
                - Carb Counting Guide
                """)
            
            with st.expander("⚠️ Awareness"):
                st.warning("""
                ### Important Reminders
                
                **Medication Safety:**
                - Take medications exactly as prescribed
                - Store medications properly
                - Check expiration dates
                
                **Warning Signs:**
                - Watch for signs of low blood sugar
                - Monitor for injection site reactions
                - Track any side effects
                
                **When to Seek Help:**
                - Blood sugar outside target range
                - Severe side effects
                - Unusual symptoms
                """)
    
    elif st.session_state.page == "Medication Tracker":
        medication_tracker()
    
    elif st.session_state.page == "Glucose Tracker":
        glucose_tracker()
    
    elif st.session_state.page == "Community":
        st.title("Community Support")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Support Groups")
            st.write("""
            ### Local Support Groups
            - Diabetes Support Group Meetings
            - Online Community Forums
            - Peer Mentoring Programs
            
            ### Healthcare Provider Network
            - Find Certified Diabetes Educators
            - Connect with Endocrinologists
            - Pharmacy Support Services
            """)
        
        with col2:
            st.subheader("Resources")
            st.write("""
            ### Community Events
            - Educational Workshops
            - Fitness Classes
            - Cooking Demonstrations
            
            ### Support Services
            - Transportation Assistance
            - Medical Supply Resources
            - Financial Aid Programs
            """)
    
    elif st.session_state.page == "Resources":
        st.title("Resources")
        
        tabs = st.tabs(["Educational Materials", "Videos", "Downloads"])
        
        with tabs[0]:
            st.header("Educational Materials")
            st.write("""
            ### Diabetes Management
            - Understanding Type 1 and Type 2 Diabetes
            - Nutrition Guidelines
            - Exercise Recommendations
            
            ### Medication Information
            - Types of Insulin
            - Oral Medications
            - Proper Storage and Handling
            """)
        
        with tabs[1]:
            st.header("Video Resources")
            st.write("""
            ### Tutorial Videos
            - Blood Sugar Testing
            - Insulin Injection Techniques
            - Using Your Glucose Meter
            
            ### Educational Series
            - Living Well with Diabetes
            - Nutrition Basics
            - Exercise Safety
            """)
        
        with tabs[2]:
            st.header("Downloads")
            st.write("""
            ### Printable Resources
            - Blood Sugar Log
            - Medication Schedule
            - Meal Planning Guide
            
            ### Tools and Charts
            - Carb Counting Guide
            - A1C Tracker
            - Exercise Log
            """)
    
    elif st.session_state.page == "Settings":
        st.title("Settings")
        
        st.subheader("Notification Settings")
        notification_time = st.time_input("Set Default Reminder Time")
        st.checkbox("Enable Daily Reminders")
        st.checkbox("Enable Low Blood Sugar Alerts")
        
        st.subheader("Profile Settings")
        st.text_input("Name")
        st.text_input("Email")
        st.selectbox("Preferred Language", ["English", "Spanish", "French"])
        
        st.subheader("Medical Information")
        st.text_input("Healthcare Provider")
        st.text_input("Emergency Contact")
        
        if st.button("Save Settings", key="save_settings_button"):
            st.success("Settings saved successfully!")

if __name__ == "__main__":
    main()