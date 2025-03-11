from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import qrcode
import pandas as pd
from flask_mail import Mail, Message
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_email_password'

# Initialize Extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
mail = Mail(app)

# ================== MODELS ==================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'admin' or 'student'

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    roll_no = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    marks = db.relationship('Marks', backref='student', lazy=True)

class Marks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(50), nullable=False)
    marks = db.Column(db.Integer, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================== ROUTES ==================

# 🔹 Home Route
@app.route('/')
def index():
    return render_template('index.html')

# 🔹 Admin and Student Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        user = User(email=email, password=hashed_password, role=role)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

# 🔹 Admin and Student Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid email or password', 'danger')

    return render_template('login.html')

# 🔹 Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# 🔹 Admin Dashboard
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('student_dashboard'))
    
    students = Student.query.all()
    return render_template('admin_dashboard.html', students=students)

# 🔹 Student Dashboard
@app.route('/student_dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return redirect(url_for('admin_dashboard'))
    
    student = Student.query.filter_by(email=current_user.email).first()
    return render_template('student_dashboard.html', student=student)

# 🔹 Add Student
@app.route('/add_student', methods=['POST'])
@login_required
def add_student():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    name = request.form['name']
    roll_no = request.form['roll_no']
    email = request.form['email']

    if Student.query.filter_by(roll_no=roll_no).first():
        flash("Roll number already exists!", "danger")
        return redirect(url_for('admin_dashboard'))

    student = Student(name=name, roll_no=roll_no, email=email)
    db.session.add(student)
    db.session.commit()

    flash('Student added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# 🔹 Update Student
@app.route('/update_student/<int:student_id>', methods=['POST'])
@login_required
def update_student(student_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    student = Student.query.get_or_404(student_id)
    student.name = request.form['name']
    student.email = request.form['email']
    db.session.commit()

    flash("Student details updated!", "success")
    return redirect(url_for('admin_dashboard'))

# 🔹 Delete Student
@app.route('/delete_student/<int:student_id>')
@login_required
def delete_student(student_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()

    flash("Student deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))

# 🔹 Bulk Upload (CSV)
@app.route('/upload_students', methods=['POST'])
@login_required
def upload_students():
    if 'file' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('admin_dashboard'))

    file = request.files['file']
    df = pd.read_csv(file)

    for _, row in df.iterrows():
        if not Student.query.filter_by(roll_no=row['Roll No']).first():
            student = Student(name=row['Name'], roll_no=row['Roll No'], email=row['Email'])
            db.session.add(student)

    db.session.commit()
    flash('Students uploaded successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# 🔹 Generate Marksheet (PDF + QR Code)
@app.route('/generate_marksheet/<int:student_id>')
@login_required
def generate_marksheet(student_id):
    student = Student.query.get_or_404(student_id)

    pdf_filename = f"marksheet_{student.roll_no}.pdf"
    pdf_path = os.path.join("static/marksheets", pdf_filename)
    qr_path = os.path.join("static/qrcodes", f"qr_{student.roll_no}.png")

    verification_url = url_for('verify_marksheet', student_id=student.id, _external=True)
    qr = qrcode.make(verification_url)
    qr.save(qr_path)

    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(200, 750, "Student Marksheet")
    c.drawString(100, 700, f"Name: {student.name}")
    c.drawString(100, 680, f"Roll No: {student.roll_no}")

    c.drawImage(qr_path, 450, 650, width=100, height=100)
    c.save()

    return send_file(pdf_path, as_attachment=True)

# ================== MAIN ==================

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)
