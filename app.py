from flask import Flask, render_template, redirect, request

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/management')
def management():
    return render_template('management.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/reservation')
def reservation():
    return render_template('reservation.html')


if __name__ == '__main__':
    app.run(debug=True)