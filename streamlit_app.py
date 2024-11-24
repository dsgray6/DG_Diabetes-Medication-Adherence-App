import streamlit as st
from datetime import datetime, timedelta, time
import pandas as pd
import plotly.express as px
import sqlite3
from pathlib import Path
import calendar
import io

def admin_functions():
    st.title("Admin Functions")
    
    if st.session_state.get('is_admin', False):  # Add admin check
        with st.expander("Data Management"):
            # Clear Daily Medication entries
            if st.button("Clear Daily Medication Entries"):
                conn = create_database_connection()
                if conn:
                    try:
                        conn.execute("DELETE FROM medications WHERE med_name = 'Daily Medication'")
                        conn.commit()
                        st.success("Daily Medication entries cleared!")
                    finally:
                        conn.close()
            
            # Clear old data
            days_to_keep = st.number_input("Keep data for how many days?", min_value=1, value=30)
            if st.button("Clear Old Data"):
                conn = create_database_connection()
                if conn:
                    try:
                        conn.execute("""
                            DELETE FROM medications 
                            WHERE date < date('now', ?)
                        """, (f'-{days_to_keep} days',))
                        conn.commit()
                        st.success("Old data cleared!")
                    finally:
                        conn.close()

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
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS glucose_readings
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      glucose_level REAL,
                      reading_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
        conn.execute('''CREATE TABLE IF NOT EXISTS medications
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      med_name TEXT,
                      dosage REAL,
                      time_taken TIMESTAMP,
                      date DATE)''')
    
        conn.execute('''CREATE TABLE IF NOT EXISTS user_accounts
                     (user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      full_name TEXT,
                      username TEXT UNIQUE,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
        conn.execute('''CREATE TABLE IF NOT EXISTS provider_messages
                     (message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      patient_id INTEGER,
                      provider_id INTEGER,
                      message_content TEXT,
                      sender_type TEXT,
                      sent_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (patient_id) REFERENCES user_accounts(user_id),
                      FOREIGN KEY (provider_id) REFERENCES user_accounts(user_id))''')
    
        conn.execute('''CREATE TABLE IF NOT EXISTS treatment_plans
                     (plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      patient_id INTEGER,
                      provider_id INTEGER,
                      plan_content TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
        conn.execute('''CREATE TABLE IF NOT EXISTS community_posts
                     (post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      content TEXT,
                      post_type TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (user_id) REFERENCES user_accounts(user_id))''')
    
        conn.execute('''CREATE TABLE IF NOT EXISTS post_comments
                     (comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      post_id INTEGER,
                      user_id INTEGER,
                      content TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (post_id) REFERENCES community_posts(post_id),
                      FOREIGN KEY (user_id) REFERENCES user_accounts(user_id))''')
        conn.commit()
    except Exception as e:
        st.error(f"Error creating/updating tables: {e}")

def log_medication(user_id, med_name, dosage, time_taken, date):
    conn = create_database_connection()
    if conn:
        try:
            with conn:
                # Convert time_taken to string format
                time_str = time_taken.strftime('%H:%M:%S')
                conn.execute("""
                    INSERT INTO medications 
                    (user_id, med_name, dosage, time_taken, date)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, med_name, dosage, time_str, date))
                conn.commit()
            return True
        except Exception as e:
            st.error(f"Error logging medication: {e}")
            return False
        finally:
            conn.close()
    return False

def log_glucose(user_id, glucose_level):
    conn = create_database_connection()
    if conn:
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO glucose_readings 
                    (user_id, glucose_level, reading_time)
                    VALUES (?, ?, datetime('now'))
                ''', (user_id, glucose_level))
                conn.commit()
                return True
        except Exception as e:
            st.error(f"Error logging glucose level: {e}")
            return False
        finally:
            conn.close()
    return False

def sign_out():
    if st.session_state.get('is_anonymous', False):
        conn = create_database_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM medications WHERE user_id = ?", 
                             (st.session_state.anonymous_id,))
                cursor.execute("DELETE FROM glucose_readings WHERE user_id = ?", 
                             (st.session_state.anonymous_id,))
                conn.commit()
            except Exception as e:
                st.error(f"Error cleaning up anonymous data: {e}")
            finally:
                conn.close()

    # Reset all session state variables
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    # Reinitialize session state
    initialize_session_state()
    st.rerun()

    # Reset all session state variables
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    # Reinitialize session state
    initialize_session_state()
    st.rerun()

def user_auth():
    if not st.session_state.authenticated:
        tab1, tab2, tab3 = st.tabs(["Sign In", "Sign Up", "Anonymous"])
        
        with tab1:
            username = st.text_input("Username", key="signin_username")
            if st.button("Sign In"):
                conn = create_database_connection()
                if conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT user_id FROM user_accounts WHERE username = ?", 
                                     (username,))
                        result = cursor.fetchone()
                        if result:
                            cursor.execute("SELECT full_name FROM user_accounts WHERE user_id = ?", (result[0],))
                            full_name = cursor.fetchone()[0]
                            st.session_state.authenticated = True
                            st.session_state.user_id = result[0]
                            st.session_state.username = username
                            st.session_state.full_name = full_name  # Store full name in session
                            st.session_state.is_anonymous = False
                            st.rerun()
                        else:
                            st.error("Invalid username")
                    finally:
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
                        st.session_state.username = new_username  # Set the username
                        st.success("Account created successfully!")
                    except sqlite3.IntegrityError:
                        st.error("Username already exists")
                    finally:
                        conn.close()
        
        with tab3:
            st.write("Browse as anonymous user")
            if st.button("Continue as Anonymous"):
                timestamp = datetime.now().strftime("%m%d_%H")
                anonymous_id = f"anon_{timestamp}"
                st.session_state.authenticated = True
                st.session_state.user_id = anonymous_id
                st.session_state.username = f"Anonymous_{timestamp}"  # Set anonymous username
                st.session_state.is_anonymous = True
                st.session_state.anonymous_id = anonymous_id
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
    
    med_name = st.selectbox("Medication", ["Insulin", "Metformin", "Other"], key="med_name_select")
    if med_name == "Other":
        med_name = st.text_input("Enter medication name")
    
    dosage = st.number_input("Dosage (mL)", min_value=0.0)
    
    time_taken = st.time_input("Time Taken")
    
    if st.button("Log Medication"):
        success = log_medication(st.session_state.user_id, med_name, dosage, time_taken, datetime.now().date())
        if success:
            st.success("Medication logged successfully!")

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
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date, med_name, dosage, time_taken 
                FROM medications 
                WHERE user_id = ? 
                AND strftime('%Y-%m', date) = ?
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
        except Exception as e:
            st.error(f"Error displaying medication calendar: {e}")
        finally:
            conn.close()

def display_recent_medications():
    conn = create_database_connection()
    if conn:
        try:
            med_data = pd.read_sql_query("""
                SELECT med_name, dosage, time_taken, date 
                FROM medications 
                WHERE user_id = ? 
                AND med_name != 'Daily Medication'
                ORDER BY date DESC, time_taken DESC
                LIMIT 10
            """, conn, params=(st.session_state.user_id,))
            
            if not med_data.empty:
                st.dataframe(med_data)
            else:
                st.info("No recent medication records")
                
        except Exception as e:
            st.error(f"Error displaying medications: {e}")
        finally:
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
        
        # Add clickable sections with detailed information
        with st.expander("Types of Insulin"):
            st.write("""
            ### Rapid-acting insulin
            - Starts working: 15 minutes
            - Peak effect: 1 hour
            - Duration: 2-4 hours
            [Learn more](https://www.diabetes.org/healthy-living/medication-treatments/insulin-other-injectables/insulin-basics)
            
            ### Short-acting insulin
            - Starts working: 30 minutes
            - Peak effect: 2-3 hours
            - Duration: 3-6 hours
            [Learn more](https://www.diabetes.org/healthy-living/medication-treatments/insulin-other-injectables/insulin-basics)
            """)
        
        with st.expander("Oral Medications"):
            st.write("""
            ### Metformin
            - Primary first-line medication
            - How it works: Reduces glucose production
            [Detailed Information](https://medlineplus.gov/druginfo/meds/a696005.html)
            
            ### Sulfonylureas
            - Increases insulin production
            - Common brands: Glipizide, Glyburide
            [Learn more](https://medlineplus.gov/druginfo/meds/a684060.html)
            """)
    
    with tab2:
        st.header("Proper Injection Techniques")
        
        # Add interactive content
        st.write("""
        ### Step-by-Step Guide
        1. Clean the injection site
        2. Pinch the skin
        3. Insert the needle at a 90-degree angle
        4. Slowly inject the insulin
        5. Wait 5-10 seconds before removing the needle
        
        [Watch Video Tutorial](https://www.diabetes.org/healthy-living/medication-treatments/insulin-other-injectables/insulin-injection-resources)
        """)
        
        with st.expander("Injection Site Rotation"):
            st.image("https://placeholder-image-url.com/injection-sites.jpg")
            st.write("""
            Proper rotation of injection sites is crucial to prevent lipohypertrophy.
            [Download Rotation Guide](https://professional.diabetes.org/sites/professional.diabetes.org/files/media/insulin_injection_reference_guide.pdf)
            """)
    
    with tab3:
        st.header("Storage Guidelines")
        
        # Add practical storage information
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Unopened Insulin")
            st.write("""
            - Store in refrigerator (36-46°F)
            - Do not freeze
            - Keep until expiration date
            [Storage Guidelines](https://www.fda.gov/drugs/emergency-preparedness/insulin-storage-and-switching-between-products-emergency)
            """)
        
        with col2:
            st.subheader("In-Use Insulin")
            st.write("""
            - Can be stored at room temperature
            - Use within 28 days
            - Keep away from direct heat and light
            [Daily Storage Tips](https://www.diabetes.org/healthy-living/medication-treatments/insulin-other-injectables/insulin-storage-and-safety)
            """)

def create_analytics_charts(patient_id, timeframe, conn):
    st.subheader(f"Analytics for {timeframe[1]}")
    
    try:
        # Glucose Analysis
        glucose_data = pd.read_sql_query("""
            SELECT glucose_level, reading_time, 
                   strftime('%H', reading_time) as hour,
                   strftime('%Y-%m-%d', reading_time) as date
            FROM glucose_readings
            WHERE user_id = ? 
            AND reading_time >= datetime('now', ?)
            ORDER BY reading_time DESC
        """, conn, params=(patient_id, timeframe[0]))
        
        if not glucose_data.empty:
            # Daily Average Chart
            daily_avg = glucose_data.groupby('date')['glucose_level'].agg(['mean', 'min', 'max']).reset_index()
            
            fig_daily = px.line(daily_avg, x='date', y='mean',
                               title='Daily Average Glucose Levels',
                               labels={'mean': 'Glucose Level (mg/dL)', 'date': 'Date'})
            fig_daily.add_scatter(x=daily_avg['date'], y=daily_avg['max'], name='Max',
                                line=dict(dash='dash'))
            fig_daily.add_scatter(x=daily_avg['date'], y=daily_avg['min'], name='Min',
                                line=dict(dash='dash'))
            st.plotly_chart(fig_daily)
            
            # Time of Day Analysis
            hourly_avg = glucose_data.groupby('hour')['glucose_level'].mean().reset_index()
            fig_hourly = px.bar(hourly_avg, x='hour', y='glucose_level',
                               title='Average Glucose by Hour of Day',
                               labels={'glucose_level': 'Glucose Level (mg/dL)', 'hour': 'Hour'})
            st.plotly_chart(fig_hourly)
            
            # Statistics
            col1, col2, col3 = st.columns(3)
            col1.metric("Average Glucose", f"{glucose_data['glucose_level'].mean():.1f} mg/dL")
            col2.metric("High Readings (>180)", len(glucose_data[glucose_data['glucose_level'] > 180]))
            col3.metric("Low Readings (<70)", len(glucose_data[glucose_data['glucose_level'] < 70]))
        else:
            st.info("No glucose data available for this timeframe")
        
        # Medication Adherence
        med_data = pd.read_sql_query("""
            SELECT med_name, date, time_taken
            FROM medications
            WHERE user_id = ?
            AND date >= date('now', ?)
            ORDER BY date DESC, time_taken DESC
        """, conn, params=(patient_id, timeframe[0]))
        
        if not med_data.empty:
            # Medication Adherence Chart
            med_counts = med_data.groupby(['date', 'med_name']).size().reset_index(name='count')
            fig_meds = px.bar(med_counts, x='date', y='count', color='med_name',
                             title='Daily Medication Adherence',
                             labels={'count': 'Times Taken', 'date': 'Date'})
            st.plotly_chart(fig_meds)
        else:
            st.info("No medication data available for this timeframe")
            
        return glucose_data, med_data
        
    except Exception as e:
        st.error(f"Error creating analytics charts: {e}")
        return None, None

def detailed_analytics_tab(patient_id):
    if not patient_id:
        st.warning("No patient selected")
        return
    st.title("Detailed Analytics")
    
    # Timeframe selection
    timeframe_options = [
        ("-7 days", "Past Week"),
        ("-30 days", "Past Month"),
        ("-90 days", "Past 3 Months"),
        ("-365 days", "Past Year")
    ]
    
    selected_timeframe = st.selectbox(
        "Select Analysis Period",
        options=timeframe_options,
        format_func=lambda x: x[1]
    )
    
    conn = create_database_connection()
    if conn:
        try:
            glucose_data, med_data = create_analytics_charts(
                patient_id, 
                selected_timeframe,
                conn
            )
            
            # Export Data Option
            if glucose_data is not None or med_data is not None:
                if st.button("Export Analytics Report"):
                    try:
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            if glucose_data is not None:
                                glucose_data.to_excel(writer, sheet_name='Glucose Data', index=False)
                            if med_data is not None:
                                med_data.to_excel(writer, sheet_name='Medication Data', index=False)
                        
                        buffer.seek(0)
                        st.download_button(
                            label="Download Excel Report",
                            data=buffer,
                            file_name=f"patient_analytics_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error(f"Error creating Excel report: {e}")
                        
        except Exception as e:
            st.error(f"Error in detailed analytics: {e}")
        finally:
            conn.close()
    else:
        st.error("Database connection failed")

def patient_messages():
    st.subheader("Healthcare Provider Messages")
    
    conn = create_database_connection()
    if conn:
        try:
            messages = pd.read_sql_query("""
                SELECT message_content, sent_time, sender_type
                FROM provider_messages
                WHERE patient_id = ?
                ORDER BY sent_time DESC
            """, conn, params=(st.session_state.user_id,))
            
            if not messages.empty:
                for _, msg in messages.iterrows():
                    with st.chat_message(msg['sender_type']):
                        st.write(msg['message_content'])
                        st.caption(msg['sent_time'])
            
            # Allow patients to send messages to their provider
            new_message = st.text_area("Message to Healthcare Provider")
            if st.button("Send Message"):
                if new_message.strip():
                    conn.execute("""
                        INSERT INTO provider_messages 
                        (patient_id, message_content, sender_type)
                        VALUES (?, ?, 'patient')
                    """, (st.session_state.user_id, new_message))
                    conn.commit()
                    st.success("Message sent!")
                    st.rerun()
        finally:
            conn.close()

def display_provider_messages_patient():
    st.subheader("Healthcare Provider Messages")
    
    conn = create_database_connection()
    if conn:
        try:
            messages = pd.read_sql_query("""
                SELECT 
                    pm.message_content, 
                    pm.sent_time, 
                    pm.sender_type,
                    CASE 
                        WHEN pm.sender_type = 'provider' THEN 
                            (SELECT full_name FROM user_accounts WHERE user_id = pm.provider_id)
                        ELSE 'You'
                    END as sender_name
                FROM provider_messages pm
                WHERE pm.patient_id = ?
                ORDER BY pm.sent_time ASC
            """, conn, params=(st.session_state.user_id,))
            
            if not messages.empty:
                st.markdown("""
                    <style>
                    .provider-message {
                        background-color: #007AFF;
                        color: white;
                        padding: 10px;
                        border-radius: 15px;
                        margin: 5px 0;
                        max-width: 80%;
                        margin-left: auto;
                    }
                    .patient-message {
                        background-color: #E8E8E8;
                        padding: 10px;
                        border-radius: 15px;
                        margin: 5px 0;
                        max-width: 80%;
                    }
                    .message-name {
                        font-size: 0.8em;
                        margin-bottom: 2px;
                    }
                    .message-time {
                        font-size: 0.7em;
                        margin-top: 2px;
                    }
                    .provider-time {
                        color: rgba(255, 255, 255, 0.8);
                    }
                    .patient-time {
                        color: #999;
                    }
                    </style>
                """, unsafe_allow_html=True)
                
                for _, msg in messages.iterrows():
                    if msg['sender_type'] == 'provider':
                        st.markdown(f"""
                            <div class="provider-message">
                                <div class="message-name" style="color: rgba(255, 255, 255, 0.8);">
                                    Dr. {msg['sender_name']}
                                </div>
                                {msg['message_content']}
                                <div class="message-time provider-time">{msg['sent_time']}</div>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                            <div class="patient-message">
                                <div class="message-name" style="color: #666;">
                                    You
                                </div>
                                {msg['message_content']}
                                <div class="message-time patient-time">{msg['sent_time']}</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                # Message input
                new_message = st.text_area("Reply to your healthcare provider")
                if st.button("Send"):
                    if new_message.strip():
                        conn.execute("""
                            INSERT INTO provider_messages 
                            (patient_id, message_content, sender_type)
                            VALUES (?, ?, 'patient')
                        """, (st.session_state.user_id, new_message))
                        conn.commit()
                        st.rerun()
            else:
                st.info("No messages from your healthcare provider yet.")
                
        except Exception as e:
            st.error(f"Error displaying messages: {e}")
        finally:
            conn.close()

def community_chat():
    st.title("Chat")
    
    # Create new post
    with st.expander("Create New Post"):
        post_content = st.text_area("Share your thoughts or ask a question")
        post_type = st.selectbox("Post Type", ["General Discussion", "Question", "Support"], key="post_type_select")
        if st.button("Post", key="create_post"):
            if post_content.strip():  # Check if content is not empty
                conn = create_database_connection()
                if conn:
                    try:
                        conn.execute("""
                            INSERT INTO community_posts (user_id, content, post_type)
                            VALUES (?, ?, ?)
                        """, (st.session_state.user_id, post_content, post_type))
                        conn.commit()
                        st.success("Post created successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating post: {e}")
                    finally:
                        conn.close()
            else:
                st.warning("Please enter some content for your post")

    # Display posts
    conn = create_database_connection()
    if conn:
        try:
            # Fetch posts with user information
            posts = pd.read_sql_query("""
                SELECT p.post_id, p.content, p.created_at, u.username, u.full_name 
                FROM community_posts p
                LEFT JOIN user_accounts u ON p.user_id = u.user_id
                ORDER BY p.created_at DESC
            """, conn)
            
            # Display each post
            for _, post in posts.iterrows():
                with st.container():
                    # Post header
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{post['full_name']}** (@{post['username']})")
                    with col2:
                        st.markdown(f"_{post['created_at']}_")
                    
                    # Post content
                    st.markdown(f"**{post['post_type']}**")
                    st.write(post['content'])
                    
                    # Comments section
                    with st.expander("Comments"):
                        # Fetch comments for this post
                        comments = pd.read_sql_query("""
                            SELECT 
                                c.content,
                                c.created_at,
                                u.username,
                                u.full_name
                            FROM post_comments c
                            LEFT JOIN user_accounts u ON c.user_id = u.user_id
                            WHERE c.post_id = ?
                            ORDER BY c.created_at
                        """, conn, params=(post['post_id'],))
                        
                        # Display existing comments
                        for _, comment in comments.iterrows():
                            st.markdown(f"↳ **{comment['full_name']}**: {comment['content']}")
                            st.caption(comment['created_at'])
                        
                        # Add new comment
                        new_comment = st.text_input("Add a comment", key=f"comment_{post['post_id']}")
                        if st.button("Reply", key=f"btn_{post['post_id']}"):
                            if new_comment.strip():
                                try:
                                    conn.execute("""
                                        INSERT INTO post_comments (post_id, user_id, content)
                                        VALUES (?, ?, ?)
                                    """, (post['post_id'], st.session_state.user_id, new_comment))
                                    conn.commit()
                                    st.success("Reply added!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error adding reply: {e}")
                            else:
                                st.warning("Please enter a comment before replying")
                    
                    st.markdown("---")  # Separator between posts
                    
        except Exception as e:
            st.error(f"Error loading posts: {e}")
        finally:
            conn.close()

def initialize_session_state():
    if 'page' not in st.session_state:
        st.session_state.page = 'Home'
    if 'is_provider' not in st.session_state:
        st.session_state.is_provider = False
    if 'provider_id' not in st.session_state:
        st.session_state.provider_id = None
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'is_anonymous' not in st.session_state:
        st.session_state.is_anonymous = False
    if 'anonymous_id' not in st.session_state:
        st.session_state.anonymous_id = None
    if 'username' not in st.session_state:
        st.session_state.username = None

def add_treatment_plan(patient_id, provider_id):
    st.subheader("Create Treatment Plan")
    plan_content = st.text_area("Plan Details")
    medications = st.text_area("Prescribed Medications")
    follow_up = st.date_input("Follow-up Date")

    if st.button("Save Treatment Plan"):
        conn = create_database_connection()
        if conn:
            try:
                conn.execute("""
                    INSERT INTO treatment_plans 
                    (patient_id, provider_id, plan_content, medications, follow_up_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (patient_id, provider_id, plan_content, medications, follow_up))
                conn.commit()
                st.success("Treatment plan saved!")
            except Exception as e:
                st.error(f"Error saving plan: {e}")
            finally:
                conn.close()

def view_patient_data(patient_id, conn):
    st.subheader("Patient Data Overview")
    # Glucose readings
    glucose_data = pd.read_sql_query("""
        SELECT glucose_level, reading_time 
        FROM glucose_readings 
        WHERE user_id = ? 
        ORDER BY reading_time DESC
    """, conn, params=(patient_id,))

    # Medication history
    med_data = pd.read_sql_query("""
        SELECT med_name, dosage, time_taken, date 
        FROM medications 
        WHERE user_id = ? 
        ORDER BY date DESC, time_taken DESC
    """, conn, params=(patient_id,))

    # Display data
    col1, col2 = st.columns(2)
    with col1:
        st.write("Glucose Readings")
        st.dataframe(glucose_data)
    with col2:
        st.write("Medication History")
        st.dataframe(med_data)

def healthcare_provider_section():
    st.title("Healthcare Provider Portal")
    
    conn = create_database_connection()
    if conn is None:
        st.error("Failed to connect to database")
        return

    try:
        # Provider authentication
        if not st.session_state.get('is_provider', False):
            col1, col2 = st.columns(2)
            
            with col1:
                provider_id = st.text_input("Provider ID")
                provider_code = st.text_input("Access Code", type="password")
            
            if st.button("Access Provider Portal"):
                if provider_code == "provider123":
                    st.session_state.is_provider = True
                    st.session_state.provider_id = provider_id
                    cursor = conn.cursor()
                    cursor.execute("SELECT full_name FROM user_accounts WHERE user_id = ?", (provider_id,))
                    provider_name = cursor.fetchone()
                    if provider_name:
                        st.session_state.provider_name = provider_name[0]
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            return

        # Only proceed if provider is authenticated
        if st.session_state.get('is_provider', False):
            # Get list of patients
            patients_query = """
                SELECT DISTINCT u.user_id, u.full_name, u.username,
                COALESCE((SELECT COUNT(*) FROM glucose_readings g WHERE g.user_id = u.user_id), 0) as reading_count,
                COALESCE((SELECT COUNT(*) FROM medications m WHERE m.user_id = u.user_id), 0) as med_count
                FROM user_accounts u
                LEFT JOIN glucose_readings g ON u.user_id = g.user_id
                LEFT JOIN medications m ON u.user_id = m.user_id
                GROUP BY u.user_id, u.full_name, u.username
                ORDER BY u.full_name
            """
            patients = pd.read_sql_query(patients_query, conn)

            # Create tabs
            tabs = st.tabs(["Patient Overview", "Detailed Analytics", "Communication", "Treatment Plans"])

            # Patient selection in sidebar
            with st.sidebar:
                if len(patients) > 0:  # Check length instead of using .empty
                    selected_username = st.selectbox(
                        "Select Patient",
                        options=patients['username'].tolist(),
                        format_func=lambda x: f"{patients[patients['username'] == x]['full_name'].iloc[0]} ({x})",
                        key="provider_patient_select"
                    )
                    
                    # Get patient ID from selection
                    patient_mask = patients['username'] == selected_username
                    if any(patient_mask):  # Use any() instead of direct DataFrame evaluation
                        patient_id = int(patients.loc[patient_mask, 'user_id'].iloc[0])
                        st.session_state.current_patient_id = patient_id
                else:
                    st.warning("No patients found in the database")
                    return
            # Proceed with tabs if we have a current patient
            if st.session_state.get('current_patient_id'):
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
                        glucose_data = pd.read_sql_query(glucose_query, conn, params=(st.session_state.current_patient_id,))
                        
                        if not glucose_data.empty:
                            glucose_data['reading_time'] = pd.to_datetime(glucose_data['reading_time'])
                            
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
                            
                            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
                            metrics_col1.metric("Average Glucose", f"{avg_glucose:.1f} mg/dL")
                            metrics_col2.metric("High Readings", high_readings)
                            metrics_col3.metric("Low Readings", low_readings)
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
                        med_data = pd.read_sql_query(med_query, conn, params=(st.session_state.current_patient_id,))
                        
                        if not med_data.empty:
                            st.dataframe(med_data, use_container_width=True)
                        else:
                            st.info("No medication records available")

                # Tab 2: Detailed Analytics
                with tabs[1]:
                    detailed_analytics_tab(st.session_state.current_patient_id)

                # Tab 3: Communication
                with tabs[2]:  # Communication tab
                    st.subheader("Patient Communication")
                    
                    # Get patient name for display
                    patient_name = patients[patients['user_id'] == st.session_state.current_patient_id]['full_name'].iloc[0]
                    st.write(f"Conversation with {patient_name}")
                    
                    # Updated query to properly get provider name
                    messages = pd.read_sql_query("""
                        SELECT 
                            pm.message_content, 
                            pm.sent_time, 
                            pm.sender_type,
                            CASE 
                                WHEN pm.sender_type = 'provider' THEN 
                                    (SELECT full_name FROM user_accounts WHERE user_id = pm.provider_id)
                                WHEN pm.sender_type = 'patient' THEN 
                                    (SELECT full_name FROM user_accounts WHERE user_id = pm.patient_id)
                            END as sender_name,
                            pm.provider_id,
                            pm.patient_id
                        FROM provider_messages pm
                        WHERE pm.patient_id = ?
                        ORDER BY pm.sent_time ASC
                    """, conn, params=(st.session_state.current_patient_id,))
                    
                    # Create message container with custom CSS
                    st.markdown("""
                        <style>
                        .provider-message {
                            background-color: #007AFF;
                            color: white;
                            padding: 10px;
                            border-radius: 15px;
                            margin: 5px 0;
                            max-width: 80%;
                            margin-left: auto;
                        }
                        .patient-message {
                            background-color: #E8E8E8;
                            padding: 10px;
                            border-radius: 15px;
                            margin: 5px 0;
                            max-width: 80%;
                        }
                        .message-name {
                            font-size: 0.8em;
                            margin-bottom: 2px;
                        }
                        .message-time {
                            font-size: 0.7em;
                            margin-top: 2px;
                        }
                        .provider-time {
                            color: rgba(255, 255, 255, 0.8);
                        }
                        .patient-time {
                            color: #666;
                        }
                        </style>
                    """, unsafe_allow_html=True)
                    
                    # Display messages
                    for _, msg in messages.iterrows():
                        # For provider view, reverse the message alignment
                        if msg['sender_type'] == 'provider':
                            st.markdown(f"""
                                <div class="provider-message">
                                    <div class="message-name" style="color: rgba(255, 255, 255, 0.8);">
                                        You
                                    </div>
                                    {msg['message_content']}
                                    <div class="message-time provider-time">{msg['sent_time']}</div>
                                </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                                <div class="patient-message">
                                    <div class="message-name" style="color: #666;">
                                        {patient_name}
                                    </div>
                                    {msg['message_content']}
                                    <div class="message-time patient-time">{msg['sent_time']}</div>
                                </div>
                            """, unsafe_allow_html=True)
                    
                    # Message input
                    new_message = st.text_area("Type your message")
                    if st.button("Send"):
                        if new_message.strip():
                            try:
                                conn.execute("""
                                    INSERT INTO provider_messages 
                                    (patient_id, provider_id, message_content, sender_type, read_status)
                                    VALUES (?, ?, ?, 'provider', 0)
                                """, (st.session_state.current_patient_id, 
                                     st.session_state.provider_id, 
                                     new_message))
                                conn.commit()
                                st.success("Message sent!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error sending message: {e}")

                # Tab 4: Treatment Plans
                with tabs[3]:
                    st.subheader("Treatment Plan Management")
                    try:
                        current_plan_query = """
                            SELECT plan_content, created_at
                            FROM treatment_plans
                            WHERE patient_id = ?
                            ORDER BY created_at DESC
                            LIMIT 1
                        """
                        current_plan_df = pd.read_sql_query(current_plan_query, conn, params=(patient_id,))
                        
                        if not current_plan_df.empty:
                            st.text_area("Current Treatment Plan", 
                                       value=current_plan_df['plan_content'].iloc[0],
                                       height=200,
                                       key="current_plan")
                            st.caption(f"Last updated: {current_plan_df['created_at'].iloc[0]}")
                        
                        new_plan = st.text_area("New Treatment Plan", height=200, key="new_plan")
                        if st.button("Update Treatment Plan", key="update_plan"):
                            if new_plan.strip():
                                conn.execute("""
                                    INSERT INTO treatment_plans 
                                    (patient_id, provider_id, plan_content)
                                    VALUES (?, ?, ?)
                                """, (patient_id, st.session_state.provider_id, new_plan))
                                conn.commit()
                                st.success("Treatment plan updated!")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error in treatment plans tab: {str(e)}")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
    finally:
        if conn:
            conn.close()

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
        theme = st.selectbox("Theme", ["Light", "Dark"], key="theme_select")
        glucose_unit = st.selectbox("Glucose Unit", ["mg/dL", "mmol/L"], key="unit_select")
        
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
    conn = create_database_connection()
    if conn:
        create_tables(conn)
        conn.close()

    initialize_session_state()

    if not user_auth():
        return

    # Add sign out button in sidebar if user is authenticated
    if st.session_state.authenticated:
        with st.sidebar:
            if st.button("Sign Out"):
                sign_out()
    
    # Show user status
    with st.sidebar:
        if st.session_state.authenticated:
            if st.session_state.is_anonymous:
                st.info("Browsing as Anonymous User")
            elif st.session_state.is_provider:
                st.info(f"Signed in as Provider: {st.session_state.provider_id}")
            else:
                st.info(f"Signed in as: {st.session_state.username}")
    
    if st.session_state.username:
        st.sidebar.write(f"Welcome, {st.session_state.get('full_name', st.session_state.username)}!")
    
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
        # Add admin check
        if st.session_state.get('is_admin', False):
            pages["Admin"] = "🔧"

        for page, icon in pages.items():
            if st.button(f"{icon} {page}", key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
    if not user_auth():
        return
    # Main Content
    if st.session_state.page == "Home":
        main_col1, main_col2 = st.columns([2, 1])
        
        with main_col1:
            # Timer and Medication Status
            current_time = datetime.now().strftime("%H:%M")
            st.header(f"🕐 {current_time}")
            
            # Streak Display
            conn = create_database_connection()
            if conn:
                streak = calculate_streak(conn, st.session_state.user_id)
                st.metric("Current Streak", f"{streak} days", "Keep it up! 🎯")
                conn.close()
            
            # Calendar View
            if st.session_state.authenticated and st.session_state.user_id:
                display_medication_calendar()
            else:
                st.warning("Please sign in to view medication records")
        
            # Quick Navigation section - now inside main_col1
            st.markdown("---")
            st.subheader("Quick Navigation")
        
            # Navigation buttons
            nav_col1, nav_col2 = st.columns(2)
            with nav_col1:
                if st.button("📊 Glucose Tracker", key="nav_glucose", use_container_width=True):
                    st.session_state.page = "Glucose Tracker"
                    st.rerun()
            
                if st.button("👥 Community", key="nav_community", use_container_width=True):
                    st.session_state.page = "Community"
                    st.rerun()
        
            with nav_col2:
                if st.button("💊 Medication Tracker", key="nav_medication", use_container_width=True):
                    st.session_state.page = "Medication Tracker"
                    st.rerun()
            
                if st.button("📚 Resources", key="nav_resources", use_container_width=True):
                    st.session_state.page = "Resources"
                    st.rerun()
                    
            st.markdown("---")
            display_provider_messages_patient()
        with main_col2:
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
        community_chat()
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
        st.selectbox("Preferred Language", ["English", "Spanish", "French"], key="language_select")
        
        st.subheader("Medical Information")
        st.text_input("Healthcare Provider")
        st.text_input("Emergency Contact")
        
        if st.button("Save Settings", key="save_settings_button"):
            st.success("Settings saved successfully!")    

if __name__ == "__main__":
    main()