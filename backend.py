from flask import Flask, request, render_template, redirect, url_for, session, flash
import pandas as pd
from datetime import datetime, timedelta
import calendar
import os
import hashlib
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import numpy as np
import random
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# CSV File Paths
RATION_CSV = 'ration_card_details.csv'
LOGIN_CSV = 'login_details.csv'
BOOKING_CSV = 'Booking_Details.csv'
BLOCKCHAIN_CSV = 'blockchain.csv'
DISTRIBUTOR_CSV = 'distributor_login_details.csv'
ACTIVITY_CSV = 'user_activity.csv'


# === UTILITY FUNCTIONS ===

def load_csv(file):
    """Load CSV with proper dtypes; create empty if not exists."""
    if os.path.exists(file):
        return pd.read_csv(
            file,
            dtype={
                'card_number': str,
                'centre': str,
                'code': str
            } if file == DISTRIBUTOR_CSV else {
                'card_number': str
            } if file in [RATION_CSV, LOGIN_CSV, BOOKING_CSV] else {
                'card_number': str,
                'activity_type': str,
                'details': str,
                'timestamp': str
            } if file == ACTIVITY_CSV else {
                'hash': str,
                'previous_hash': str,
                'data': str
            }
        )
    # Create empty DataFrame with correct columns
    if file == LOGIN_CSV:
        return pd.DataFrame(columns=['card_number', 'password'])
    elif file == BOOKING_CSV:
        return pd.DataFrame(columns=[
            'card_number', 'card_holder_name', 'number_of_persons_in_family',
            'booking_centre', 'date', 'session', 'current_score'
        ])
    elif file == BLOCKCHAIN_CSV:
        return pd.DataFrame(columns=['hash', 'previous_hash', 'data'])
    elif file == DISTRIBUTOR_CSV:
        return pd.DataFrame(columns=['centre', 'code'])
    elif file == ACTIVITY_CSV:
        return pd.DataFrame(columns=['card_number', 'activity_type', 'details', 'timestamp'])
    else:
        return pd.DataFrame()


def save_csv(df, file):
    """Save DataFrame to CSV."""
    df.to_csv(file, index=False)


def log_activity(card_number, activity_type, details):
    """Log user/admin activity."""
    activity_df = load_csv(ACTIVITY_CSV)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_entry = pd.DataFrame({
        'card_number': [card_number],
        'activity_type': [activity_type],
        'details': [details],
        'timestamp': [timestamp]
    })
    activity_df = pd.concat([activity_df, new_entry], ignore_index=True)
    save_csv(activity_df, ACTIVITY_CSV)


def get_current_month_year():
    """Return current month in 'YYYY-MM' format."""
    return datetime.now().strftime('%Y-%m')


def get_booking_count(centre, date, session_time):
    """Count bookings for a given centre, date, and session."""
    booking_df = load_csv(BOOKING_CSV)
    return len(booking_df[
                   (booking_df['booking_centre'] == centre) &
                   (booking_df['date'] == date) &
                   (booking_df['session'] == session_time)
                   ])


def add_to_blockchain(data):
    """Append data to blockchain log with hash chaining."""
    blockchain_df = load_csv(BLOCKCHAIN_CSV)
    previous_hash = blockchain_df['hash'].iloc[-1] if not blockchain_df.empty else '0000'
    new_hash = hashlib.sha256((previous_hash + data).encode()).hexdigest()
    new_entry = pd.DataFrame({
        'hash': [new_hash],
        'previous_hash': [previous_hash],
        'data': [data]
    })
    blockchain_df = pd.concat([blockchain_df, new_entry], ignore_index=True)
    save_csv(blockchain_df, BLOCKCHAIN_CSV)


def forecast_demand():
    booking_df = load_csv(BOOKING_CSV)
    if booking_df.empty:
        return [], 0.0

    booking_df['date'] = pd.to_datetime(booking_df['date'], errors='coerce')
    booking_df = booking_df.dropna(subset=['date'])

    aggregated_df = booking_df.groupby('date').size().reset_index(name='count')
    aggregated_df['day'] = aggregated_df['date'].dt.dayofyear

    X = aggregated_df['day'].values.reshape(-1, 1)
    y = aggregated_df['count'].values

    if len(X) < 2:
        return [], 0.0

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = LinearRegression()
    model.fit(X_train, y_train)

    mae = mean_absolute_error(y_test, model.predict(X_test))

    # Get last real date
    last_date = aggregated_df['date'].max()

    # Generate next 7 real dates
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=7)

    # Convert to dayofyear for model input
    future_days = future_dates.dayofyear.values.reshape(-1, 1)

    forecasts = model.predict(future_days)

    forecasts = [
        (date.strftime("%Y-%m-%d"), max(0, float(round(pred))))
        for date, pred in zip(future_dates, forecasts)
    ]

    return forecasts, float(round(mae, 2))

# === MONTHLY SCORE UPDATE (Runs on Last Day of Month) ===

def update_scores():
    """Auto-update scores on the last day of every month."""
    now = datetime.now()
    last_day = calendar.monthrange(now.year, now.month)[1]

    # Only run on the last day of the month
    if now.day != last_day:
        return

    print(f"[AUTO] Running monthly score update on {now.strftime('%Y-%m-%d')}")

    ration_df = load_csv(RATION_CSV)
    booking_df = load_csv(BOOKING_CSV)
    current_month = get_current_month_year()  # e.g., "2025-10"

    updated = False
    for index, row in ration_df.iterrows():
        card_number = row['card_number']
        old_score = int(row['score'])  # Ensure integer

        # Get user's bookings in current month
        user_bookings = booking_df[booking_df['card_number'] == card_number]
        monthly_bookings = user_bookings[
            user_bookings['date'].astype(str).str.startswith(current_month, na=False)
        ]

        if len(monthly_bookings) == 0:
            new_score = max(0, old_score - 10)
        else:
            new_score = min(100, old_score + 5 if old_score <= 94 else 100)

        if new_score != old_score:
            ration_df.at[index, 'score'] = new_score
            log_activity(
                card_number, 'score_update',
                f'Score changed from {old_score} to {new_score} (monthly auto-update)'
            )
            updated = True

    if updated:
        save_csv(ration_df, RATION_CSV)
        print(f"[AUTO] Score update completed. {len(ration_df)} users processed.")
    else:
        print("[AUTO] No score changes needed this month.")


# === SCHEDULER SETUP ===

def start_scheduler():
    """Start background scheduler to run update_scores daily."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=update_scores,
        trigger='cron',
        hour=0,
        minute=5,
        id='monthly_score_update',
        replace_existing=True
    )
    scheduler.start()
    print("Scheduler started: update_scores will run daily at 00:05")
    atexit.register(lambda: scheduler.shutdown())


# === ROUTES ===

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        card_number = request.form['card_number'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('signup'))

        ration_df = load_csv(RATION_CSV)
        if card_number not in ration_df['card_number'].values:
            flash('Invalid card number')
            return redirect(url_for('signup'))

        login_df = load_csv(LOGIN_CSV)
        if card_number in login_df['card_number'].values:
            flash('Card number already registered')
            return redirect(url_for('signup'))

        otp = str(random.randint(100000, 999999))
        print(f"Mock OTP sent for signup: {otp}")

        new_entry = pd.DataFrame({'card_number': [card_number], 'password': [password]})
        login_df = pd.concat([login_df, new_entry], ignore_index=True)
        save_csv(login_df, LOGIN_CSV)
        log_activity(card_number, 'signup', 'User signed up')
        flash('Signup Successful')
        return redirect(url_for('home'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_type = request.form.get('login_type', '').strip().lower()

        if not login_type:
            flash('Please select a login type')
            return redirect(url_for('login'))

        if login_type == 'user':
            card_number = request.form.get('card_number', '').strip()
            password = request.form.get('user_password', '')

            login_df = load_csv(LOGIN_CSV)
            user = login_df[(login_df['card_number'] == card_number) & (login_df['password'] == password)]
            if user.empty:
                flash('Invalid card number or password')
                return redirect(url_for('login'))

            session['user'] = card_number
            log_activity(card_number, 'login', 'User login')
            return redirect(url_for('user_dashboard', section='profile'))

        elif login_type == 'admin':
            username = request.form.get('username', '').strip()
            password = request.form.get('admin_password', '')
            if username == 'admin' and password == '123456789':
                session['admin'] = True
                log_activity('admin', 'login', 'Admin login')
                return redirect(url_for('admin_dashboard'))
            flash('Invalid username or password')
            return redirect(url_for('login'))

        elif login_type == 'distributor':
            centre = request.form.get('centre', '').strip()
            code = request.form.get('distributor_code', '').strip()
            distributor_df = load_csv(DISTRIBUTOR_CSV)
            distributor = distributor_df[(distributor_df['centre'] == centre) & (distributor_df['code'] == code)]
            if distributor.empty:
                flash('Invalid centre or code')
                return redirect(url_for('login'))
            session['distributor'] = centre
            log_activity(centre, 'login', f'Distributor login for {centre}')
            return redirect(url_for('distributor_dashboard'))

        else:
            flash(f'Invalid login type: {login_type}')
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        card_number = request.form['card_number'].strip()
        ration_df = load_csv(RATION_CSV)
        login_df = load_csv(LOGIN_CSV)
        user = ration_df[ration_df['card_number'] == card_number]
        login_user = login_df[login_df['card_number'] == card_number]
        if not user.empty and not login_user.empty:
            mobile = user['mobile_number'].values[0]
            password = login_user['password'].values[0]
            print(f"SMS to {mobile}: Your card_number is {card_number}, password is {password}")
            log_activity(card_number, 'forgot_password', 'Password reset requested')
            flash('Password sent to your mobile number')
        else:
            flash('Invalid card number')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/user_dashboard/<section>')
def user_dashboard(section):
    if 'user' not in session:
        return redirect(url_for('home'))

    card_number = session['user']
    ration_df = load_csv(RATION_CSV)
    user_data = ration_df[ration_df['card_number'] == card_number].to_dict('records')[0]
    booking_df = load_csv(BOOKING_CSV)
    history = booking_df[booking_df['card_number'] == card_number].to_dict('records')

    centres = ['Gandi', 'Chintal', 'Shapure', 'KPHB']
    centre_locations = {
        'Gandi': 'Gandi Maisamma, Hyderabad, Telangana 500043',
        'Chintal': 'Chintal, Hyderabad, Telangana 500054',
        'Shapure': 'Shapoor Nagar, Hyderabad, Telangana 500055',
        'KPHB': 'Kukatpally Housing Board Colony, Hyderabad, Telangana 500072'
    }
    min_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
    max_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    if section == 'booking':
        if user_data['score'] < 35:
            flash('Your score is too low to book')
            return redirect(url_for('user_dashboard', section='profile'))

        booking_counts = []
        for centre in centres:
            for date in pd.date_range(min_date, max_date).strftime('%Y-%m-%d'):
                for session_time in ['Morning', 'Evening']:
                    count = get_booking_count(centre, date, session_time)
                    status = 'low' if count <= 2 else 'medium' if count <= 5 else 'high'
                    booking_counts.append({
                        'centre': centre,
                        'location': centre_locations[centre],
                        'date': date,
                        'session': session_time,
                        'count': count,
                        'status': status
                    })
        return render_template(
            'user_dashboard.html',
            section=section,
            user_data=user_data,
            history=history,
            centres=centres,
            centre_locations=centre_locations,
            min_date=min_date,
            max_date=max_date,
            booking_counts=booking_counts
        )
    return render_template(
        'user_dashboard.html',
        section=section,
        user_data=user_data,
        history=history,
        centres=centres,
        centre_locations=centre_locations,
        min_date=min_date,
        max_date=max_date,
        booking_counts=[]
    )


@app.route('/book', methods=['POST'])
def book():
    if 'user' not in session:
        return redirect(url_for('home'))

    card_number = session['user']
    centre = request.form['centre']
    date = request.form['date']
    session_time = request.form['session']

    booking_date = datetime.strptime(date, '%Y-%m-%d')
    if booking_date < datetime.now() + timedelta(days=5):
        flash('Booking must be at least 5 days in advance')
        return redirect(url_for('user_dashboard', section='booking'))

    # ==================== NEW: MAX 5 BOOKINGS CHECK ====================
    current_bookings = get_booking_count(centre, date, session_time)
    if current_bookings >= 5:
        flash('Maximum number of bookings for this slot is already completed. Please choose another slot.')
        return redirect(url_for('user_dashboard', section='booking'))
    # ===================================================================

    current_month = get_current_month_year()
    booking_df = load_csv(BOOKING_CSV)
    monthly_bookings = booking_df[
        (booking_df['card_number'] == card_number) &
        (booking_df['date'].str.startswith(current_month))
    ]
    if not monthly_bookings.empty:
        flash('You can book only once per month')
        return redirect(url_for('user_dashboard', section='booking'))

    ration_df = load_csv(RATION_CSV)
    user = ration_df[ration_df['card_number'] == card_number].iloc[0]

    data = f"{card_number},{centre},{date},{session_time}"
    add_to_blockchain(data)

    new_booking = pd.DataFrame({
        'card_number': [card_number],
        'card_holder_name': [user['card_holder_name']],
        'number_of_persons_in_family': [user['number_of_persons_in_family']],
        'booking_centre': [centre],
        'date': [date],
        'session': [session_time],
        'current_score': [user['score']]
    })
    booking_df = pd.concat([booking_df, new_booking], ignore_index=True)
    save_csv(booking_df, BOOKING_CSV)

    print(f"SMS to {user['mobile_number']}: Booking confirmed for {centre} on {date}, {session_time}.")
    log_activity(card_number, 'booking', f'Booked at {centre} on {date} {session_time}')
    flash('Booking Confirmed')
    return redirect(url_for('user_dashboard', section='profile'))


@app.route('/distributor_dashboard', methods=['GET', 'POST'])
def distributor_dashboard():
    if 'distributor' not in session:
        return redirect(url_for('home'))

    centre = session['distributor']
    booking_df = load_csv(BOOKING_CSV)
    bookings = booking_df[booking_df['booking_centre'] == centre]
    total_bookings = len(bookings)

    selected_date = request.form.get('date', None)
    card_number = request.form.get('card_number', '').strip()

    filtered_bookings = bookings
    if card_number:
        filtered_bookings = filtered_bookings[
            filtered_bookings['card_number'].str.contains(card_number, case=False, na=False)
        ]
    if selected_date:
        filtered_bookings = filtered_bookings[filtered_bookings['date'] == selected_date]

    daily_bookings = filtered_bookings.to_dict('records')
    daily_total = len(daily_bookings)

    return render_template(
        'distributor_dashboard.html',
        centre=centre,
        total_bookings=total_bookings,
        selected_date=selected_date,
        card_number=card_number,
        daily_bookings=daily_bookings,
        daily_total=daily_total
    )


@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('home'))

    forecasts, mae = forecast_demand()
    ration_df = load_csv(RATION_CSV)

    card_number = request.form.get('card_number', '').strip()
    score_filter = request.form.get('score_filter', '')

    filtered_users = ration_df
    if card_number:
        filtered_users = filtered_users[
            filtered_users['card_number'].str.contains(card_number, case=False, na=False)
        ]
    if score_filter == 'below_35':
        filtered_users = filtered_users[filtered_users['score'] < 35]
    elif score_filter == 'above_35':
        filtered_users = filtered_users[filtered_users['score'] >= 35]

    users = filtered_users.to_dict('records')

    return render_template(
        'admin_dashboard.html',
        users=users,
        forecasts=forecasts,
        mae=mae,
        card_number=card_number,
        score_filter=score_filter
    )


@app.route('/admin/user_report/<card_number>')
def admin_user_report(card_number):
    if 'admin' not in session:
        return redirect(url_for('home'))
    activity_df = load_csv(ACTIVITY_CSV)
    activities = activity_df[activity_df['card_number'] == card_number].to_dict('records')
    return render_template('user_report.html', card_number=card_number, activities=activities)


@app.route('/admin/remove/<card_number>')
def admin_remove(card_number):
    if 'admin' not in session:
        return redirect(url_for('home'))
    ration_df = load_csv(RATION_CSV)
    ration_df = ration_df[ration_df['card_number'] != card_number]
    save_csv(ration_df, RATION_CSV)

    login_df = load_csv(LOGIN_CSV)
    login_df = login_df[login_df['card_number'] != card_number]
    save_csv(login_df, LOGIN_CSV)

    flash('User removed')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/update_score', methods=['POST'])
def admin_update_score():
    if 'admin' not in session:
        return redirect(url_for('home'))

    card_number = request.form['card_number']
    new_score = int(request.form['new_score'])
    new_score = max(0, min(100, new_score))

    ration_df = load_csv(RATION_CSV)
    index = ration_df[ration_df['card_number'] == card_number].index[0]
    old_score = ration_df.at[index, 'score']
    ration_df.at[index, 'score'] = new_score
    save_csv(ration_df, RATION_CSV)

    log_activity(card_number, 'score_update', f'Score changed from {old_score} to {new_score} (admin update)')
    flash('Score updated')
    return redirect(url_for('admin_dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# === START SCHEDULER & APP ===

if __name__ == '__main__':
    start_scheduler()  # Start background job
    app.run(debug=True)

