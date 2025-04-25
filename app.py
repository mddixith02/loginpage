from flask import Flask, render_template, request, redirect, url_for, session, flash
import snowflake.connector
from datetime import datetime
import xml.etree.ElementTree as ET
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Hardcoded admin credentials (for initial access)
HARDCODED_ADMIN = {
    'username': 'admin',
    'password_hash': generate_password_hash('admin123'),  # Password: admin123
    'name': 'System Admin',
    'email': 'admin@example.com',
    'phone': '000-000-0000',
    'dob': '2000-01-01',
    'gender': 'Other',
    'place': 'Headquarters',
    'position': 'Administrator',
    'role': 'admin'
}

# Improved Snowflake connection with error handling
def get_snowflake_connection():
    try:
        conn = snowflake.connector.connect(
            user="mdd",
            password="RGYmvycj59zmnZt",
            account="XJYTWBG-BB43317",
            warehouse="Compute_WH",
            database="my_newdb",
            schema="my_newschema"
        )
        return conn
    except Exception as e:
        flash("Database connection error", "error")
        print(f"Snowflake connection error: {str(e)}")
        return None

# Modified get_user to handle both hardcoded and DB users
def get_user(username):
    # Check hardcoded admin first
    if username == HARDCODED_ADMIN['username']:
        return HARDCODED_ADMIN
    
    # Check database users
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

# Safe user fetching that always returns a list
def get_all_users():
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(snowflake.connector.DictCursor)
        cursor.execute('SELECT * FROM users')
        return cursor.fetchall() or []
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

    print("DEBUG - Data received to add:", data)

    conn = get_snowflake_connection()
    if not conn:
        return False
        
    try:
        cursor = conn.cursor()
        hashed_password = generate_password_hash(data['password'])

        print("Inserting user into DB with values:", (
            data['username'], hashed_password, data['name'], data['email'],
            data['phone'], data['dob'], data['gender'], data['place'],
            data['position'], data['role']
        ))

        cursor.execute(""" 
            INSERT INTO users (username, password_hash, name, email, phone, dob, gender, place, position, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['username'], hashed_password, data['name'], data['email'],
            data['phone'], data['dob'], data['gender'], data['place'],
            data['position'], data['role']
        ))
        conn.commit()
        print("✅ USER ADDED SUCCESSFULLY")
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
        flash("Cannot delete system admin", "error")
        return False

    conn = get_snowflake_connection()
    if not conn:
        return False
        
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
        cursor.execute("DELETE FROM reviews WHERE LOWER(username) = LOWER(%s)", (username,))
        conn.commit()
        return cursor.rowcount > 0
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
            UPDATE users SET 
                name = %s, email = %s, phone = %s, 
                dob = %s, gender = %s, place = %s, 
                position = %s, role = %s
            WHERE username = %s
        """, (
            data['name'], data['email'], data['phone'],
            data['dob'], data['gender'], data['place'],
            data['position'], data['role'], username
        ))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error updating user: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def add_feedback(email, content):
    try:
        try:
            tree = ET.parse('feedback.xml')
            root = tree.getroot()
        except FileNotFoundError:
            root = ET.Element('feedbacks')
            tree = ET.ElementTree(root)

        feedback = ET.SubElement(root, 'feedback')
        if email:
            ET.SubElement(feedback, 'email').text = email
        ET.SubElement(feedback, 'content').text = content
        ET.SubElement(feedback, 'timestamp').text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        tree.write('feedback.xml', encoding='utf-8', xml_declaration=True)
        return True
    except Exception as e:
        print(f"Error saving feedback: {str(e)}")
        return False

def get_all_feedback():
    try:
        tree = ET.parse('feedback.xml')
        return [{
            'email': feedback.find('email').text if feedback.find('email') is not None else '',
            'content': feedback.find('content').text,
            'timestamp': feedback.find('timestamp').text
        } for feedback in tree.findall('feedback')]
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"Error reading feedback: {str(e)}")
        return []

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user_type = request.form.get('user_type', 'user')

        if not username or not password:
            flash("Username and password are required", "error")
            return redirect(url_for('login'))

        user = get_user(username)
        if user and check_password_hash(user.get('password_hash') or user.get('PASSWORD_HASH'), password):
            user_role = user.get('role') or user.get('ROLE')  # Try lowercase or uppercase

            if (user_type == 'admin' and user_role == 'admin') or \
               (user_type == 'user' and user_role == 'user'):
                session['username'] = username
                session['role'] = user_role
                return redirect(url_for('admin_dashboard' if user_role == 'admin' else 'user_dashboard'))
            else:
                flash("Invalid role selection", "error")
        else:
            flash("Invalid credentials", "error")

        return redirect(url_for('login'))

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

    data = {
        'username': request.form.get('username', '').strip(),
        'password': request.form.get('password', '').strip(),
        'name': request.form.get('name', '').strip(),
        'email': request.form.get('email', '').strip(),
        'phone': request.form.get('phone', '').strip(),
        'dob': request.form.get('dob', '').strip(),
        'gender': request.form.get('gender', '').strip(),
        'place': request.form.get('place', '').strip(),
        'position': request.form.get('position', '').strip(),
        'role': request.form.get('role', '').strip()
    }

    if add_user(data):
        flash("User added successfully", "success")
    else:
        flash("Failed to add user", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/view_user/<username>')
def view_user(username):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    user = get_user(username)
    if not user:
        flash("User not found", "error")
        return redirect(url_for('admin_dashboard'))

    def safe_get(field):
        return user.get(field) or user.get(field.upper()) or "Not provided"

    profile = {
        'username': username,
        'name': safe_get('name'),
        'email': safe_get('email'),
        'phone': safe_get('phone'),
        'dob': safe_get('dob'),
        'gender': safe_get('gender'),
        'place': safe_get('place'),
        'position': safe_get('position'),
        'role': safe_get('role')
    }

    return render_template('view_user.html', profile=profile)

@app.route('/edit_user/<username>', methods=['GET', 'POST'])
def edit_user_route(username):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'email': request.form.get('email', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'dob': request.form.get('dob', '').strip(),
            'gender': request.form.get('gender', '').strip(),
            'place': request.form.get('place', '').strip(),
            'position': request.form.get('position', '').strip(),
            'role': request.form.get('role', '').strip()
        }
        if update_user(username, data):
            flash("User updated successfully", "success")
        else:
            flash("Failed to update user", "error")
        return redirect(url_for('admin_dashboard'))

    user = get_user(username)
    if not user:
        flash("User not found", "error")
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_user.html', user=user)


@app.route('/delete_user/<username>', methods=['POST'])
def delete_user_route(username):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if delete_user(username):
        flash("User deleted successfully", "success")
    else:
        flash("Failed to delete user", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/user_dashboard', methods=['GET', 'POST'])
def user_dashboard():
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))

    user = get_user(session['username'])
    if not user:
        flash("User session expired", "error")
        return redirect(url_for('login'))

    def safe_get(field):
        return user.get(field) or user.get(field.upper()) or "Not provided"

    profile = {
        'name': safe_get('name'),
        'email': safe_get('email'),
        'phone': safe_get('phone'),
        'dob': safe_get('dob'),
        'gender': safe_get('gender'),
        'place': safe_get('place'),
        'position': safe_get('position')
    }

    """ if request.method == 'POST':
        email = request.form.get('email', '').strip()
        feedback = request.form.get('feedback', '').strip()

        if not feedback:
            flash("Feedback cannot be empty", "error")
        elif add_feedback(email, feedback):
            flash("Feedback submitted successfully", "success")
        else:
            flash("Failed to submit feedback", "error")
        return redirect(url_for('user_dashboard')) """

    # Get feedback matching this user's email
    all_feedbacks = get_all_feedback()
    user_feedbacks = []
    user_email = profile['email']
    if user_email and user_email != "Not provided":
        user_feedbacks = [f for f in all_feedbacks if f['email'] == user_email]

    return render_template('user_dashboard.html',
                           username=session['username'],
                           profile=profile,
                           feedbacks=user_feedbacks)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.after_request
def prevent_back(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == '__main__':
    app.run(debug=True)
