import sqlite3
import json
import random
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, timedelta
import os

# --- Configuration ---
app = Flask(__name__)
DB_NAME = 'homework_data.db'
STUDENT_NAME = "Akash Chaudhary" 

# Admin-Adjustable Question Counts and Types
DAILY_Q_CONFIG = {
    'Monday': {'count': 3, 'type': 'Question-Answer (3-5 lines)', 'placeholder': 'Type your detailed answer here...'},
    'Tuesday': {'count': 10, 'type': 'One-Liner Question', 'placeholder': 'Type the precise one-line answer...'},
    'Wednesday': {'count': 5, 'type': 'Two-Liner Question', 'placeholder': 'Type your short, summarized answer...'},
    'Thursday': {'count': 1, 'type': 'Drawing-Based Question', 'placeholder': 'Upload your diagram/drawing (Image/PDF) or describe it here.'},
    'Friday': {'count': 2, 'type': 'Observation-Based Question', 'placeholder': 'Describe your observation and conclusion...'},
    'Saturday': {'count': 0, 'type': 'Rest Day', 'placeholder': ''},
    'Sunday': {'count': 0, 'type': 'Rest Day', 'placeholder': ''},
}

# --- Database Setup and Question Loading ---

def get_db_connection():
    """Connects to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Creates tables if they don't exist and loads 500+ dummy questions."""
    conn = get_db_connection()
    c = conn.cursor()

    # 1. Create Tables
    c.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            day_type TEXT NOT NULL,
            question_text TEXT NOT NULL,
            answer TEXT 
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS homework_log (
            id INTEGER PRIMARY KEY,
            date_given TEXT UNIQUE NOT NULL,
            day_of_week TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            answers_json TEXT 
        )
    """)
    conn.commit()

    # 2. Check and Populate Question Bank (Min 100 per day)
    
    # Simple check to prevent re-populating on every run
    total_q_count = c.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    
    if total_q_count < 500: # If less than 500 total, populate the entire bank
        print("Populating initial question bank (500+ questions)...")
        questions_to_insert = []
        
        # Generator for unique dummy questions
        def generate_questions(day, q_type, count):
            q_list = []
            for i in range(1, count + 1):
                q_text = f"[{day} - {q_type}] Q{i}: What is the role of mitochondria in a cell?"
                ans = f"Mitochondria are the powerhouse of the cell, generating ATP through cellular respiration. (Answer {i})"
                
                if day == 'Thursday': # Drawing
                     q_text = f"[{day} - {q_type}] Q{i}: Draw and label the structure of a neuron. (QID:{i})"
                elif day == 'Friday': # Observation
                     q_text = f"[{day} - {q_type}] Q{i}: Observe the burning of magnesium ribbon and list two observations. (QID:{i})"
                
                q_list.append((day, q_text, ans))
            return q_list

        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            # Ensure at least 100 questions per required day
            questions_to_insert.extend(generate_questions(day, DAILY_Q_CONFIG[day]['type'], 110))

        c.executemany("INSERT INTO questions (day_type, question_text, answer) VALUES (?, ?, ?)", questions_to_insert)
        conn.commit()
        print(f"Successfully loaded {c.execute('SELECT COUNT(*) FROM questions').fetchone()[0]} questions.")
    
    conn.close()

# Initialize DB when the app starts
with app.app_context():
    initialize_database() 

# --- Routes ---

@app.route('/')
def home():
    """Home page: Welcome and 'Start' button."""
    today = datetime.now()
    date_str = today.strftime('%Y-%m-%d')
    day_name = today.strftime('%A')
    
    conn = get_db_connection()
    # Check if homework for today is already generated
    log = conn.execute("SELECT * FROM homework_log WHERE date_given = ?", (date_str,)).fetchone()
    conn.close()
    
    is_generated = log is not None
    day_config = DAILY_Q_CONFIG.get(day_name, {'count': 0, 'type': 'Error'})
    
    return render_template('home.html', 
                           student_name=STUDENT_NAME,
                           day_name=day_name,
                           date_str=today.strftime('%d %B, %Y'),
                           is_generated=is_generated,
                           DAILY_Q_CONFIG=DAILY_Q_CONFIG,
                           day_config=day_config)

@app.route('/generate_questions', methods=['POST'])
def generate_questions():
    """Generates questions based on the current day and logs them."""
    today = datetime.now()
    date_str = today.strftime('%Y-%m-%d')
    day_name = today.strftime('%A')
    
    q_info = DAILY_Q_CONFIG.get(day_name, {'count': 0})
    required_count = q_info['count']
    
    if required_count == 0:
        return redirect(url_for('view_todays_questions')) # Redirects to view the "Rest Day" message

    conn = get_db_connection()
    
    # 1. Check if already generated today
    if conn.execute("SELECT * FROM homework_log WHERE date_given = ?", (date_str,)).fetchone():
        conn.close()
        return redirect(url_for('view_todays_questions'))

    # 2. Get questions from the bank
    bank_questions = conn.execute("SELECT id, question_text FROM questions WHERE day_type = ?", (day_name,)).fetchall()
    
    if len(bank_questions) < required_count:
        conn.close()
        # Fallback to an error page or a message
        return render_template('error.html', message=f"⚠️ Error: Not enough questions in the {day_name} bank!")
        
    # Select random questions (ensuring uniqueness)
    selected_questions = random.sample(bank_questions, required_count)
    
    # 3. Log the assignment
    q_data = [{'id': q['id'], 'text': q['question_text'], 'submitted_answer': ''} for q in selected_questions]
    
    conn.execute("INSERT INTO homework_log (date_given, day_of_week, questions_json, answers_json) VALUES (?, ?, ?, ?)",
                 (date_str, day_name, json.dumps(q_data), json.dumps([])))
    conn.commit()
    conn.close()
    
    return redirect(url_for('view_todays_questions'))

@app.route('/today')
def view_todays_questions():
    """Displays the generated questions for today."""
    date_str = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    log = conn.execute("SELECT * FROM homework_log WHERE date_given = ?", (date_str,)).fetchone()
    conn.close()
    
    day_name = datetime.now().strftime('%A')
    day_config = DAILY_Q_CONFIG.get(day_name)

    if day_config and day_config['count'] == 0:
        return render_template('homework.html', day_name=day_name, message="🎉 Today is a rest day! Enjoy your break.", questions=[])
        
    if not log:
        # Not generated yet
        return redirect(url_for('home'))

    questions = json.loads(log['questions_json'])
    
    # Determine the input type and placeholder based on the day config
    input_type = 'file' if day_name == 'Thursday' else 'textarea'
    placeholder = day_config['placeholder'] if day_config else 'Type your answer...'

    # Check if answers have been submitted
    is_submitted = any(q.get('submitted_answer') for q in questions)
    
    return render_template('homework.html', 
                           day_name=day_name, 
                           questions=questions,
                           log_id=log['id'],
                           input_type=input_type,
                           placeholder=placeholder,
                           is_submitted=is_submitted)

@app.route('/submit_answers/<int:log_id>', methods=['POST'])
def submit_answers(log_id):
    """Saves the student's answers to the log."""
    conn = get_db_connection()
    log = conn.execute("SELECT * FROM homework_log WHERE id = ?", (log_id,)).fetchone()
    
    if not log:
        conn.close()
        return "Error: Assignment not found", 404

    current_questions = json.loads(log['questions_json'])
    
    # Process submissions
    for i, q in enumerate(current_questions):
        answer_key = f'answer_{i+1}'
        submitted_answer = request.form.get(answer_key, '') # Get text answer
        
        # Handle Drawing upload (Thursday) - Simplified: saves filename/description
        if datetime.strptime(log['date_given'], '%Y-%m-%d').strftime('%A') == 'Thursday':
             # In a real app, this would handle file storage (e.g., in a directory)
             if 'file' in request.files and request.files['file'].filename != '':
                 submitted_answer = f"File uploaded: {request.files['file'].filename}"
             else:
                 submitted_answer = submitted_answer or 'No file uploaded, only description provided.'

        q['submitted_answer'] = submitted_answer if submitted_answer else 'N/A (Not Submitted)'

    # Update the homework_log record
    conn.execute("UPDATE homework_log SET questions_json = ? WHERE id = ?", 
                 (json.dumps(current_questions), log_id))
    conn.commit()
    conn.close()

    return redirect(url_for('view_todays_questions'))

@app.route('/record')
def record_menu():
    """Displays a list of all previous assignments."""
    conn = get_db_connection()
    logs = conn.execute("SELECT id, date_given, day_of_week, questions_json FROM homework_log ORDER BY date_given DESC").fetchall()
    conn.close()
    
    processed_logs = []
    for log in logs:
        questions = json.loads(log['questions_json'])
        # Check if any answer has been recorded
        is_answered = any(q.get('submitted_answer') for q in questions)
        processed_logs.append({
            'id': log['id'],
            'date_given': log['date_given'],
            'day_of_week': log['day_of_week'],
            'is_answered': is_answered
        })
        
    return render_template('record.html', logs=processed_logs)

@app.route('/record/<int:log_id>')
def view_record(log_id):
    """Displays a specific log (questions and submitted answers)."""
    conn = get_db_connection()
    log = conn.execute("SELECT * FROM homework_log WHERE id = ?", (log_id,)).fetchone()
    
    if not log:
        conn.close()
        return "Log not found", 404

    questions_with_answers = json.loads(log['questions_json'])
    
    # Fetch the original correct answer from the question bank for comparison
    for q in questions_with_answers:
        original = conn.execute("SELECT answer FROM questions WHERE id = ?", (q['id'],)).fetchone()
        q['correct_answer'] = original['answer'] if original else "N/A"
        
    conn.close()

    return render_template('view_record.html', 
                           log=log, 
                           questions=questions_with_answers,
                           day_type=DAILY_Q_CONFIG.get(log['day_of_week'])['type'])

# --- Custom Error Handler ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', message="404 - Page Not Found. Did you take a wrong turn?"), 404

if __name__ == '__main__':
    # Flask requires the secret key for session management (good practice, though not strictly needed for this app)
    app.secret_key = os.urandom(24) 
    print(f"Starting server at http://127.0.0.1:5000/")
    app.run(debug=True)
