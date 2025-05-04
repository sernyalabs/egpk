from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', b'4a6c29b227f7468e82f79b053c70f8b6')  # Use default if .env is not found

# Initialize Supabase client
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(url, key)

# Root route (index) - checks if logged in or not
@app.route('/')
def index():
    if 'username' in session:  # If the user is logged in
        return redirect(url_for('home'))  # Redirect to the home page
    return redirect(url_for('login'))  # Otherwise, redirect to the login page

# Sign up route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone_number = request.form['phone_number']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        # Insert new user into Supabase
        response = supabase.table('users').insert([{
            'first_name': first_name,
            'last_name': last_name,
            'phone_number': phone_number,
            'email': email,
            'username': username,
            'password': password_hash,
        }]).execute()

        if response.data:
            return redirect(url_for('login'))
        else:
            return f"Signup failed: {response.error_message}"

    return render_template('signup.html')


# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None  # Initialize error variable
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Get the user from the database
        user = supabase.table('users').select('*').eq('username', username).execute()

        if user.data and check_password_hash(user.data[0]['password'], password):
            session['username'] = username
            return redirect(url_for('home'))  # Redirect to home page after successful login
        else:
            error = "Invalid username or password"

    return render_template('login.html', error=error)


@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in
    return render_template('home.html', username=session['username'])

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    # Fetch user data from Supabase
    user_data = supabase.table('users').select('*').eq('username', session['username']).execute()

    if request.method == 'POST':
        # Handle profile update (e.g., update username or password)
        new_username = request.form['username']
        new_password = request.form['password']

        # Check if password was provided, hash it if it's changed
        if new_password:
            new_password_hash = generate_password_hash(new_password)
        else:
            new_password_hash = user_data.data[0]['password']  # Keep the current password if no new one

        # Update user data in Supabase
        update_response = supabase.table('users').update({
            'username': new_username,
            'password': new_password_hash
        }).eq('username', session['username']).execute()

        # Check if the update was successful based on the response data
        if update_response.data:
            session['username'] = new_username  # Update the session with the new username
            return redirect(url_for('profile'))  # Reload the profile page after update
        else:
            # If update failed, show error message
            return f"Error updating profile: {update_response.error_message}"

    return render_template('profile.html', user_data=user_data.data[0])  # Render profile page with user data

# Logout route
@app.route('/logout')
def logout():
    session.pop('username', None)  # Remove the username from the session
    return redirect(url_for('login'))  # Redirect to login page after logout

# Dashboard route
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return "<h1>Dashboard - Under Construction</h1>"

##Grievances
@app.route('/grievances')
def grievances():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in
    return render_template('grievances.html')  # or whatever the content is



# About route
@app.route('/about')
def about():
    return render_template('about.html')

# Route to handle the submission of new grievances
@app.route('/new_grievance', methods=['GET', 'POST'])
def new_grievance():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        username = session['username']  # Get the logged-in user's username

        # Insert the grievance into the database
        response = supabase.table('grievances').insert([{
            'title': title,
            'description': description,
            'username': username
        }]).execute()

        if response.data:
            return redirect(url_for('my_grievances'))  # Redirect to the user's grievances page
        else:
            return f"Failed to submit grievance: {response.error_message}"

    return render_template('new_grievance.html')  # Render the form to create a new grievance

# Route to view the user's grievances
@app.route('/my_grievances')
def my_grievances():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    # Fetch grievances from the database for the logged-in user
    grievances_data = supabase.table('grievances').select('*').eq('username', session['username']).execute()

    return render_template('my_grievances.html', grievances=grievances_data.data)  # Render with user's grievances

if __name__ == '__main__':
    app.run(debug=True)
