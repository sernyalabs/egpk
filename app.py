from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import text

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
            'job_role' : 'user',
        }]).execute()

        if response.data:
            return redirect(url_for('login'))
        else:
            return f"Signup failed: {response.error_message}"

    return render_template('signup.html')

# Route for login
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None  # Initialize error variable

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Fetch user from Supabase
        user_response = supabase.table('users').select('*').eq('username', username).execute()

        if user_response.data:
            user = user_response.data[0]

            # Verify password
            if check_password_hash(user['password'], password):
                session['username'] = username
                session['role'] = user.get('job_role', 'user')  # default to 'user' if not set

                # Redirect based on role
                if user.get('job_role', '').lower() == 'admin':
                    return redirect(url_for('admin_panel'))
                else:
                    return redirect(url_for('home'))
            else:
                error = "Invalid username or password"
        else:
            error = "Invalid username or password"

    return render_template('login.html', error=error)


#Route for home
@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    role = session.get('role')
    
    if role == 'admin':
        return redirect(url_for('admin_panel'))  # Redirect admin to admin panel
    else:
        return render_template('home.html', username=session['username'])  # Show user home

#Route for profile
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
    session.pop('username', None)  # Remove the username from session
    session.pop('role', None)      # Remove the role from session
    return redirect(url_for('login'))  # Redirect to login page


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
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        username = session['username']

        # Insert grievance
        grievance_response = supabase.table('grievances').insert([{
            'title': title,
            'description': description,
            'username': username,
            'status': 'Pending'
        }]).execute()

        if grievance_response.data:
            # Find admin user(s) - assuming job_role='admin'
            admins_resp = supabase.table('users').select('username').eq('job_role', 'admin').execute()
            if admins_resp.data and len(admins_resp.data) > 0:
                # Send message to each admin found
                messages_to_insert = []
                for admin_user in admins_resp.data:
                    messages_to_insert.append({
                        'sender_username': username,
                        'receiver_username': admin_user['username'],
                        'subject': title,
                        'message': description
                    })
                message_response = supabase.table('messages').insert(messages_to_insert).execute()
                # You can check message_response for errors if you want

            # If no admins found, just do nothing silently

            return redirect(url_for('my_grievances'))
        else:
            return f"Failed to submit grievance: {grievance_response.error_message}"

    return render_template('new_grievance.html')


# Route to view the user's grievances
@app.route('/my_grievances')
def my_grievances():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    # Fetch grievances from the database for the logged-in user
    grievances_data = supabase.table('grievances').select('*').eq('username', session['username']).execute()

    return render_template('my_grievances.html', grievances=grievances_data.data)  # Render with user's grievances

# Route for admin panel
@app.route('/admin_panel')
def admin_panel():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    # Count grievances with status = 'Addressed'
    addressed_response = supabase.table('grievances').select('id', count='exact').eq('status', 'Addressed').execute()
    total_addressed = addressed_response.count or 0

    # Count grievances with status = 'Pending'
    pending_response = supabase.table('grievances').select('id', count='exact').eq('status', 'Pending').execute()
    total_pending = pending_response.count or 0

    # Count grievances with status = 'In Progress'
    progress_response = supabase.table('grievances').select('id', count='exact').eq('status', 'In Progress').execute()
    total_in_progress = progress_response.count or 0

    return render_template(
        'admin_panel.html',
        total_addressed=total_addressed,
        total_pending=total_pending,
        total_in_progress=total_in_progress
    )


# Route for admin grievance management
@app.route('/admin_grievance_management')
def admin_grievance_management():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    status_filter = request.args.get('status')  # Read filter from URL
    query = supabase.table('grievances').select('*').order('created_at', desc=True)

    if status_filter:
        query = query.eq('status', status_filter)

    response = query.execute()
    grievances = response.data if response.data else []

    return render_template('admin_grievance_management.html', grievances=grievances, selected_status=status_filter)

# Handle Reply and Status Update
@app.route('/reply_grievance/<int:grievance_id>', methods=['POST'])
def reply_grievance(grievance_id):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    reply = request.form.get('reply')
    new_status = request.form.get('status')

    # Fetch grievance details
    grievance_resp = supabase.table('grievances').select('*').eq('id', grievance_id).execute()
    if not grievance_resp.data:
        return "Grievance not found.", 404

    grievance = grievance_resp.data[0]
    username = grievance['username']

    # Update grievance status
    supabase.table('grievances').update({'status': new_status}).eq('id', grievance_id).execute()

    # Send reply as message to the user
    supabase.table('messages').insert([{
        'sender_username': 'admin',
        'receiver_username': username,
        'subject': f"Reply to: {grievance['title']}",
        'message': reply
    }]).execute()

    return redirect(url_for('admin_grievance_management'))

# Route for admin inbox
@app.route('/admin_inbox')
def admin_inbox():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    # Fetch messages where the admin is the receiver
    messages_response = supabase.table('messages')\
        .select('sender_username, message, timestampz')\
        .eq('receiver_username', session['username'])\
        .order('timestampz', desc=True)\
        .execute()

    messages = messages_response.data if messages_response.data else []

    return render_template('admin_inbox.html', messages=messages)


#Route for admin account management
@app.route('/admin/account_management')
def admin_account_management():
    # Check if logged in and admin
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    # Fetch all users from Supabase
    response = supabase.table('users').select('*').execute()

    users = response.data if response.data else []

    # Convert is_active to boolean if needed (depends on how stored in DB)
    for user in users:
        # For safety, ensure is_active is boolean; adjust this as per your DB schema
        if 'is_active' in user:
            user['is_active'] = True if user['is_active'] in [True, 'true', 'True', 1] else False
        else:
            user['is_active'] = True  # Default true if field missing

    return render_template('admin_account_management.html', users=users)

#Route to handle updates of a user's role and active status
@app.route('/admin_update_user/<int:user_id>', methods=['POST'])
def admin_update_user(user_id):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    job_role = request.form.get('job_role')
    is_active_str = request.form.get('is_active')
    is_active = is_active_str.lower() == 'true'

    try:
        response = supabase.table('users').update({
            'job_role': job_role,
            'is_active': is_active
        }).eq('id', user_id).execute()

        # Success if response.data is not empty
        if response.data:
            flash("User updated successfully!", "success")
        else:
            flash("Failed to update user. No changes applied.", "error")
    except Exception as e:
        flash(f"Failed to update user: {str(e)}", "error")

    return redirect(url_for('admin_account_management'))



#Route for user inbox
@app.route('/user_inbox')
def user_inbox():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    response = supabase.table('messages').select('*').eq('receiver_username', username).order('timestampz', desc=True).execute()
    messages = response.data if response.data else []

    return render_template('user_inbox.html', messages=messages)

#Route for deleting user
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    response = supabase.table("users").delete().eq("id", user_id).execute()

    if response.data and len(response.data) > 0:
        flash('User deleted successfully.', 'success')
    else:
        flash('User not found or failed to delete.', 'error')

    return redirect(url_for('admin_account_management'))

# Route to delete grievance
@app.route('/admin/delete_grievance/<int:grievance_id>', methods=['POST'])
def delete_grievance(grievance_id):
    response = supabase.table("grievances").delete().eq("id", grievance_id).execute()

    if response.data and len(response.data) > 0:
        flash('Grievance deleted successfully.', 'success')
    else:
        flash('Failed to delete grievance.', 'error')

    return redirect(url_for('admin_grievance_management'))


if __name__ == '__main__':
    app.run(debug=True)
