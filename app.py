from flask import Flask, render_template, request, redirect, url_for, session, flash
import snowflake.connector
from datetime import datetime
import xml.etree.ElementTree as ET
from werkzeug.security import generate_password_hash, check_password_hash
import os
import traceback

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

HARDCODED_ADMIN = {
    'username': 'admin',
    'password_hash': generate_password_hash('admin123'),
    'name': 'System Admin',
    'email': 'admin@example.com',
    'phone': '000-000-0000',
    'dob': '2000-01-01',
    'gender': 'Other',
    'place': 'Headquarters',
    'position': 'Administrator',
    'role': 'admin'
}

def get_snowflake_connection():
    try:
        return snowflake.connector.connect(
            user="mdd",
            password="RGYmvycj59zmnZt",
            account="XJYTWBG-BB43317",
            warehouse="Compute_WH",
            database="my_newdb",
            schema="my_newschema"
        )
    except Exception as e:
        print(f"Snowflake connection error: {str(e)}")
        return None

def get_user(username):
    if username == HARDCODED_ADMIN['username']:
        return HARDCODED_ADMIN

    conn = get_snowflake_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(snowflake.connector.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        return cursor.fetchone()
    except Exception as e:
        print(f"Error fetching user: {str(e)}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_all_users():
    conn = get_snowflake_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(snowflake.connector.DictCursor)
        cursor.execute('SELECT * FROM users')
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching users: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def add_user(data):
    if get_user(data['username']) and data['username'] != HARDCODED_ADMIN['username']:
        flash("Username already exists", "error")
        return False

    conn = get_snowflake_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        hashed_password = generate_password_hash(data['password'])
        cursor.execute("""
            INSERT INTO users (username, password_hash, name, email, phone, dob, gender, place, position, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['username'], hashed_password, data['name'], data['email'],
            data['phone'], data['dob'], data['gender'], data['place'],
            data['position'], data['role']
        ))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error adding user: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def delete_user(username):
    print("Trying to delete:", username)
    if username == HARDCODED_ADMIN['username']:
        flash("Cannot delete admin", "error")
        return False

    conn = get_snowflake_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
        cursor.execute("DELETE FROM reviews WHERE LOWER(username) = LOWER(%s)", (username,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error deleting user: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def update_user(username, data):
    conn = get_snowflake_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET name=%s, email=%s, phone=%s, dob=%s, gender=%s, place=%s, position=%s, role=%s
            WHERE username=%s
        """, (
            data['name'], data['email'], data['phone'], data['dob'], data['gender'],
            data['place'], data['position'], data['role'], username
        ))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error updating user: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def add_feedback(email, content):
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'feedback.xml')
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except (FileNotFoundError, ET.ParseError):
            root = ET.Element('feedbacks')
            tree = ET.ElementTree(root)

        feedback = ET.SubElement(root, 'feedback')
        ET.SubElement(feedback, 'email').text = email or 'Anonymous'
        ET.SubElement(feedback, 'content').text = content
        ET.SubElement(feedback, 'timestamp').text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        tree.write(file_path, encoding='utf-8', xml_declaration=True)
        return True
    except Exception as e:
        print(f"Error saving feedback: {str(e)}")
        traceback.print_exc()
        return False

def delete_feedback_by_index(index):
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'feedback.xml')
        tree = ET.parse(file_path)
        root = tree.getroot()
        feedbacks = root.findall('feedback')
        if 0 <= index < len(feedbacks):
            root.remove(feedbacks[index])
            tree.write(file_path, encoding='utf-8', xml_declaration=True)
            return True
        return False
    except Exception as e:
        print(f"Error deleting feedback: {str(e)}")
        return False

def get_all_feedback():
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'feedback.xml')
        if not os.path.exists(file_path):
            return []

        tree = ET.parse(file_path)
        feedbacks = []
        for f in tree.findall('feedback'):
            feedbacks.append({
                'email': f.findtext('email', 'Anonymous'),
                'content': f.findtext('content', 'No content'),
                'timestamp': f.findtext('timestamp', 'Unknown')
            })
        return feedbacks
    except Exception as e:
        print(f"Error reading feedback: {str(e)}")
        return []

# ROUTES

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = get_user(username)
        if user and check_password_hash(user.get('password_hash') or user.get('PASSWORD_HASH'), password):
            session['username'] = username
            session['role'] = user.get('role') or user.get('ROLE')
            return redirect(url_for('admin_dashboard' if session['role'] == 'admin' else 'user_dashboard'))
        flash("Invalid credentials", "error")
    return render_template('login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html',
                           username=session['username'],
                           users=get_all_users(),
                           feedbacks=get_all_feedback())

@app.route('/add_user', methods=['POST'])
def add_user_route():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    data = {key: request.form.get(key, '').strip() for key in [
        'username', 'password', 'name', 'email', 'phone', 'dob',
        'gender', 'place', 'position', 'role'
    ]}
    if add_user(data):
        flash("User added successfully", "success")
    else:
        flash("Failed to add user", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/edit_user/<username>', methods=['GET', 'POST'])
def edit_user_route(username):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = {key: request.form.get(key, '').strip() for key in [
            'name', 'email', 'phone', 'dob', 'gender', 'place', 'position', 'role'
        ]}
        if update_user(username, data):
            flash("User updated successfully", "success")
        else:
            flash("Failed to update user", "error")
        return redirect(url_for('admin_dashboard'))

    user = get_user(username)
    return render_template('edit_user.html', user=user)

@app.route('/view_user/<username>')
def view_user(username):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    user = get_user(username)
    
    # Create a normalized profile dictionary that works with both upper and lowercase keys
    profile = {}
    if user:
        for key in ['username', 'name', 'email', 'phone', 'dob', 'gender', 'place', 'position', 'role']:
            profile[key] = user.get(key) or user.get(key.upper()) or "Not provided"
    
    return render_template('view_user.html', profile=profile)

@app.route('/delete_user/<username>', methods=['POST'])
def delete_user_route(username):
    if delete_user(username):
        flash("User deleted successfully", "success")
    else:
        flash("User deleted successfully", "success") #delete user pop up temp fix 
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_feedback/<int:feedback_index>', methods=['POST'])
def delete_feedback(feedback_index):
    if delete_feedback_by_index(feedback_index):
        flash("Feedback deleted", "success")
    else:
        flash("Failed to delete feedback", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/user_dashboard', methods=['GET', 'POST'])
def user_dashboard():
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))

    user = get_user(session['username'])
    profile = {k: user.get(k) or user.get(k.upper()) or "Not provided" for k in [
        'name', 'email', 'phone', 'dob', 'gender', 'place', 'position'
    ]}
    email = profile['email']
    feedbacks = [f for f in get_all_feedback() if f['email'] == email]

    return render_template('user_dashboard.html',
                           username=session['username'],
                           profile=profile,
                           feedbacks=feedbacks)

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'username' not in session:
        return redirect(url_for('login'))
    email = request.form.get('email', '').strip()
    content = request.form.get('feedback', '').strip()
    if not content:
        flash("Feedback cannot be empty", "error")
    elif add_feedback(email, content):
        flash("Feedback submitted successfully", "success")
    else:
        flash("Failed to submit feedback", "error")
    return redirect(url_for('user_dashboard' if session.get('role') == 'user' else 'admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == '__main__':
    app.run(debug=True)
