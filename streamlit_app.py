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
    conn.execute('''CREATE TABLE IF NOT EXISTS user_accounts
                 (user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  full_name TEXT,
                  username TEXT UNIQUE,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS community_posts
                 (post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  content TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS post_comments
                 (comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  post_id INTEGER,
                  user_id INTEGER,
                  content TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    conn.execute('''CREATE TABLE IF NOT EXISTS provider_messages
                 (message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  patient_id INTEGER,
                  provider_id INTEGER,
                  message_content TEXT,
                  sender_type TEXT,
                  sent_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS treatment_plans
                 (plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  patient_id INTEGER,
                  provider_id INTEGER,
                  plan_content TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

def user_auth():
    # Make sure session state is initialized
    initialize_session_state()
    
    if not st.session_state['authenticated']:
        tab1, tab2, tab3 = st.tabs(["Sign In", "Sign Up", "Anonymous"])
        
        with tab1:
            username = st.text_input("Username", key="signin_username")
            if st.button("Sign In"):
                conn = create_database_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id FROM user_accounts WHERE username = ?", 
                                 (username,))
                    result = cursor.fetchone()
                    if result:
                        st.session_state['authenticated'] = True
                        st.session_state['user_id'] = result[0]
                        st.session_state['username'] = username
                        st.rerun()
                    else:
                        st.error("Invalid username")
                    conn.close()
        
        with tab2:
            full_name = st.text_input("Full Name")
            new_username = st.text_input("Username", key="signup_username")
            if st.button("Sign Up"):
                conn = create_database_connection()
                if conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO user_accounts (full_name, username)
                            VALUES (?, ?)
                        """, (full_name, new_username))
                        conn.commit()
                        st.success("Account created successfully!")
                    except sqlite3.IntegrityError:
                        st.error("Username already exists")
                    finally:
                        conn.close()
        
        with tab3:
            st.write("Browse as anonymous user")
            if st.button("Continue as Anonymous"):
                st.session_state['authenticated'] = True
                st.session_state['user_id'] = "anonymous"
                st.session_state['username'] = "Anonymous User"
                st.rerun()
        
        return False
    return True

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
def process_glucose_data(df):
    df['reading_time'] = pd.to_datetime(df['reading_time'])
    df['hour'] = df['reading_time'].dt.floor('h')
    hourly_avg = df.groupby('hour')['glucose_level'].mean().reset_index()
    return hourly_avg

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
            hourly_data = process_glucose_data(df)
            
            fig = px.line(hourly_data, x='hour', y='glucose_level',
                         title='Average Hourly Glucose Levels')
            fig.update_layout(
                xaxis_title="Time",
                yaxis_title="Glucose Level (mg/dL)",
                height=400
            )
            
            # Add danger thresholds
            fig.add_hline(y=180, line_dash="dash", line_color="red",
                         annotation_text="High Risk")
            fig.add_hline(y=70, line_dash="dash", line_color="red",
                         annotation_text="Low Risk")
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Warning messages
            latest_glucose = df['glucose_level'].iloc[-1]
            if latest_glucose > 180:
                st.warning("⚠️ High glucose level detected! Please check with your healthcare provider.")
            elif latest_glucose < 70:
                st.warning("⚠️ Low glucose level detected! Please take immediate action.")
        else:
            st.info("No glucose readings available yet.")
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

def medication_info_pages():
    st.title("Medication Information")
    
    tab1, tab2, tab3 = st.tabs([
        "Understanding Your Medication",
        "Proper Injection Techniques",
        "Storage Guidelines"
    ])
    
    with tab1:
        st.header("Understanding Your Diabetes Medication")
        st.write("""
        ### Types of Insulin
        - Rapid-acting insulin
        - Short-acting insulin
        - Intermediate-acting insulin
        - Long-acting insulin
        
        ### Oral Medications
        - Metformin
        - Sulfonylureas
        - DPP-4 inhibitors
        """)
    
    with tab2:
        st.header("Proper Injection Techniques")
        st.write("""
        ### Step-by-Step Guide
        1. Clean the injection site
        2. Pinch the skin
        3. Insert the needle at a 90-degree angle
        4. Slowly inject the insulin
        5. Wait 5-10 seconds before removing the needle
        """)
    
    with tab3:
        st.header("Storage Guidelines")
        st.write("""
        ### Proper Storage
        - Keep insulin in the refrigerator (36-46°F)
        - In-use insulin can be stored at room temperature
        - Avoid extreme temperatures
        - Check expiration dates regularly
        """)

def community_chat():
    st.title("Community Support")
    
    # Create new post
    with st.expander("Create New Post"):
        post_content = st.text_area("Share your thoughts")
        if st.button("Post"):
            conn = create_database_connection()
            if conn:
                try:
                    conn.execute("""
                        INSERT INTO community_posts (user_id, content)
                        VALUES (?, ?)
                    """, (st.session_state.user_id, post_content))
                    conn.commit()
                    st.success("Post created successfully!")
                finally:
                    conn.close()
    
    # Display posts
    conn = create_database_connection()
    if conn:
        posts = pd.read_sql_query("""
            SELECT p.*, u.username 
            FROM community_posts p
            JOIN user_accounts u ON p.user_id = u.user_id
            ORDER BY p.created_at DESC
        """, conn)
        
        for _, post in posts.iterrows():
            st.write(f"**{post['username']}** - {post['created_at']}")
            st.write(post['content'])
            
            # Comments section
            with st.expander("Comments"):
                comments = pd.read_sql_query("""
                    SELECT c.*, u.username 
                    FROM post_comments c
                    JOIN user_accounts u ON c.user_id = u.user_id
                    WHERE c.post_id = ?
                    ORDER BY c.created_at
                """, conn, params=(post['post_id'],))
                
                for _, comment in comments.iterrows():
                    st.write(f"↳ **{comment['username']}**: {comment['content']}")
                
                # Add new comment form
                new_comment = st.text_input("Add a comment", key=f"comment_{post['post_id']}")
                if st.button("Comment", key=f"btn_{post['post_id']}"):
                    try:
                        conn.execute("""
                            INSERT INTO post_comments (post_id, user_id, content)
                            VALUES (?, ?, ?)
                        """, (post['post_id'], st.session_state.user_id, new_comment))
                        conn.commit()
                        st.success("Comment added!")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Error adding comment: {e}")
        conn.close()

def initialize_session_state():
    # Initialize all required session state variables
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = 'default_user'
    if 'is_provider' not in st.session_state:
        st.session_state.is_provider = False
    if 'page' not in st.session_state:
        st.session_state.page = "Home"
    if 'provider_id' not in st.session_state:
        st.session_state.provider_id = None

def healthcare_provider_section():
    st.title("Healthcare Provider Portal")

    conn = None    

    try:
        # Only show login if not authenticated as provider
        if not st.session_state.get('is_provider', False):
            col1, col2 = st.columns(2)
            
            with col1:
                provider_id = st.text_input("Provider ID")
                provider_code = st.text_input("Access Code", type="password")
            
            with col2:
                st.markdown("""
                #### Provider Access
                - Secure access to patient records
                - Comprehensive patient monitoring 
                - Direct patient communication
                """)
            
            if st.button("Access Provider Portal"):
                if provider_code == "provider123":
                    st.session_state.is_provider = True
                    st.session_state.provider_id = provider_id
                    st.rerun()
                else:
                    st.error("Invalid credentials")
                return
        
        # Only proceed if provider is authenticated
        if st.session_state.get('is_provider', False):
            # Create database connection first
            conn = create_database_connection()
            if conn is None:
                st.error("Failed to connect to database")
                return
            
            # Create tabs
            tabs = st.tabs([
                "Patient Overview",
                "Detailed Analytics",
                "Communication",
                "Treatment Plans"
            ])
            
            # Get list of patients
            try:
                patients_query = """
                    SELECT DISTINCT u.user_id, u.full_name, u.username,
                    (SELECT COUNT(*) FROM glucose_readings g WHERE g.user_id = u.user_id) as reading_count,
                    (SELECT COUNT(*) FROM medications m WHERE m.user_id = u.user_id) as med_count
                    FROM user_accounts u
                    ORDER BY u.full_name
                """
                patients = pd.read_sql_query(patients_query, conn)

                if patients.empty:
                    st.warning("No patients found in the database")
                    return

                # Patient selection sidebar
                with st.sidebar:
                    st.subheader("Patient Selection")
                    selected_patient = st.selectbox(
                        "Select Patient",
                        options=patients['username'].tolist(),
                        format_func=lambda x: f"{patients[patients['username'] == x]['full_name'].iloc[0]} ({x})"
                    )
                    
                    if selected_patient:
                        patient_data = patients[patients['username'] == selected_patient].iloc[0]
                        st.info(f"""
                        **Patient Statistics:**
                        - Glucose Readings: {patient_data['reading_count']}
                        - Medication Logs: {patient_data['med_count']}
                        """)

                if selected_patient:
                    patient_id = patients[patients['username'] == selected_patient]['user_id'].iloc[0]
                    
                    # Tab 1: Patient Overview
                    with tabs[0]:
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.subheader("Glucose Trends")
                            glucose_query = """
                                SELECT glucose_level, reading_time,
                                CASE 
                                    WHEN glucose_level > 180 THEN 'High'
                                    WHEN glucose_level < 70 THEN 'Low'
                                    ELSE 'Normal'
                                END as status
                                FROM glucose_readings
                                WHERE user_id = ?
                                AND reading_time >= date('now', '-30 days')
                                ORDER BY reading_time DESC
                            """
                            glucose_data = pd.read_sql_query(glucose_query, conn, params=(patient_id,))
                            
                            if not glucose_data.empty:
                                fig = px.line(glucose_data, 
                                            x='reading_time', 
                                            y='glucose_level',
                                            color='status',
                                            title='30-Day Glucose Trends')
                                fig.add_hline(y=180, line_dash="dash", line_color="red")
                                fig.add_hline(y=70, line_dash="dash", line_color="red")
                                st.plotly_chart(fig, use_container_width=True)
                                
                                avg_glucose = glucose_data['glucose_level'].mean()
                                high_readings = len(glucose_data[glucose_data['glucose_level'] > 180])
                                low_readings = len(glucose_data[glucose_data['glucose_level'] < 70])
                                
                                st.metric("Average Glucose", f"{avg_glucose:.1f} mg/dL")
                                col1, col2 = st.columns(2)
                                col1.metric("High Readings", high_readings)
                                col2.metric("Low Readings", low_readings)
                            else:
                                st.info("No glucose readings available for this patient")
                        
                        with col2:
                            st.subheader("Recent Medications")
                            med_query = """
                                SELECT med_name, dosage, time_taken, date
                                FROM medications
                                WHERE user_id = ?
                                ORDER BY date DESC, time_taken DESC
                                LIMIT 10
                            """
                            med_data = pd.read_sql_query(med_query, conn, params=(patient_id,))
                            
                            if not med_data.empty:
                                st.dataframe(med_data, use_container_width=True)
                            else:
                                st.info("No medication records available")
                
            except Exception as e:
                st.error(f"An error occurred while accessing patient data: {str(e)}")
            
            finally:
                if conn:
                    conn.close()

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

        # Tab 2: Detailed Analytics
        with tabs[1]:
            st.subheader("Advanced Analytics")
            
            # Time period selection
            period = st.selectbox(
                "Analysis Period",
                ["Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom Range"]
            )
            
            if period == "Custom Range":
                col1, col2 = st.columns(2)
                start_date = col1.date_input("Start Date")
                end_date = col2.date_input("End Date")
            
            # Analysis type selection
            analysis_type = st.multiselect(
                "Select Analysis Types",
                ["Glucose Patterns", "Medication Adherence", "Time in Range", "Correlation Analysis"]
            )
            
            if "Glucose Patterns" in analysis_type:
                st.subheader("Glucose Patterns")
                # Add detailed glucose pattern analysis
                
            if "Medication Adherence" in analysis_type:
                st.subheader("Medication Adherence")
                # Add medication adherence analysis

        # Tab 3: Communication
        with tabs[2]:
            st.subheader("Patient Communication")
            
            # Message history
            messages = pd.read_sql_query("""
                SELECT message_content, sent_time, sender_type
                FROM provider_messages
                WHERE patient_id = ?
                ORDER BY sent_time DESC
            """, conn, params=(patient_id,))
            
            if not messages.empty:
                for _, msg in messages.iterrows():
                    with st.chat_message(msg['sender_type']):
                        st.write(msg['message_content'])
                        st.caption(msg['sent_time'])
            
            # New message
            new_message = st.text_area("New Message")
            if st.button("Send Message"):
                try:
                    conn.execute("""
                        INSERT INTO provider_messages 
                        (patient_id, provider_id, message_content, sender_type)
                        VALUES (?, ?, ?, 'provider')
                    """, (patient_id, st.session_state.provider_id, new_message))
                    conn.commit()
                    st.success("Message sent!")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error sending message: {e}")

        # Tab 4: Treatment Plans
        with tabs[3]:
            st.subheader("Treatment Plan Management")
            
            # Current treatment plan
            current_plan = st.text_area(
                "Current Treatment Plan",
                height=200
            )
            
            # Medication adjustments
            st.subheader("Medication Adjustments")
            col1, col2, col3 = st.columns(3)
            with col1:
                med_name = st.selectbox("Medication", ["Insulin", "Metformin", "Other"])
            with col2:
                dosage = st.number_input("New Dosage")
            with col3:
                frequency = st.selectbox("Frequency", ["Once daily", "Twice daily", "As needed"])
            
            if st.button("Update Treatment Plan"):
                # Save treatment plan updates
                pass
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        
    finally:
        # Safely close connection if it exists
        if conn is not None:
            try:
                conn.close()
            except Exception as e:
                st.error(f"Error closing database connection: {str(e)}")
# Enhanced settings section
def settings():
    st.title("Settings")
    
    tabs = st.tabs(["Reminders", "Profile", "Preferences"])
    
    with tabs[0]:
        st.header("Reminder Settings")
        
        # Multiple reminder times
        st.subheader("Set Reminder Times")
        num_reminders = st.number_input("Number of daily reminders", 1, 10, 3)
        
        reminder_times = []
        for i in range(num_reminders):
            time = st.time_input(f"Reminder {i+1}", key=f"reminder_{i}")
            reminder_times.append(time)
        
        # Delay options
        st.subheader("Reminder Delay Options")
        delay_options = [5, 10, 15, 30, 60]
        selected_delays = []
        for delay in delay_options:
            if st.checkbox(f"{delay} minutes"):
                selected_delays.append(delay)
        
        if st.button("Save Reminder Settings"):
            conn = create_database_connection()
            if conn:
                try:
                    # Clear existing reminders
                    conn.execute("""
                        DELETE FROM reminder_settings
                        WHERE user_id = ?
                    """, (st.session_state.user_id,))
                    
                    # Save new reminders
                    for time in reminder_times:
                        conn.execute("""
                            INSERT INTO reminder_settings (user_id, reminder_time)
                            VALUES (?, ?)
                        """, (st.session_state.user_id, time.strftime('%H:%M')))
                    
                    conn.commit()
                    st.success("Reminder settings saved!")
                except Exception as e:
                    st.error(f"Error saving settings: {e}")
                finally:
                    conn.close()
    
    with tabs[1]:
        st.header("Profile Settings")
        
        # User information
        current_name = st.text_input("Full Name")
        email = st.text_input("Email Address")
        phone = st.text_input("Phone Number")
        
        # Emergency contacts
        st.subheader("Emergency Contacts")
        contact_name = st.text_input("Contact Name")
        contact_phone = st.text_input("Contact Phone")
        
        if st.button("Update Profile"):
            # Save profile information to database
            pass
    
    with tabs[2]:
        st.header("Preferences")
        
        # Display preferences
        st.subheader("Display Settings")
        theme = st.selectbox("Theme", ["Light", "Dark"])
        glucose_unit = st.selectbox("Glucose Unit", ["mg/dL", "mmol/L"])
        
        # Notification preferences
        st.subheader("Notifications")
        st.checkbox("Email Notifications")
        st.checkbox("SMS Notifications")
        st.checkbox("Push Notifications")
        
        if st.button("Save Preferences"):
            # Save preferences to database
            pass

def main():
    st.set_page_config(
        page_title="Diabetes Support App",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    initialize_session_state()

    if not user_auth():
        return
    
    if st.session_state.username:
        st.sidebar.write(f"Welcome, {st.session_state.username}!")
    
    # Sidebar Navigation
    with st.sidebar:
        st.title("Navigation")
        pages = {
            "Home": "🏠",
            "Medication Tracker": "💊",
            "Glucose Tracker": "📊",
            "Community": "👥",
            "Resources": "📚",
            "Settings": "⚙️",
            "Healthcare Provider": "👨‍⚕️"
        }
        
        for page, icon in pages.items():
            if st.button(f"{icon} {page}", key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
    if not user_auth():
        return
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
    
    elif st.session_state.page == "Healthcare Provider":
        healthcare_provider_section()

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