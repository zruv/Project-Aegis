from flask import Flask, render_template, request, redirect, url_for
import os
import sqlite3
from cryptography.fernet import Fernet
import base64
import hashlib

app = Flask(__name__)

# Configuration
DB_PATH = '/data/aegis.db'
# In a real scenario, this key comes from the "Watcher" injecting it.
# For now, we'll default to a dev key if not provided.
MASTER_KEY = os.environ.get('AEGIS_MASTER_KEY', 'default_insecure_dev_key_12345')

def get_fernet():
    # Derive a 32-byte url-safe base64 encoded key from the master key
    key = hashlib.sha256(MASTER_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS credentials
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  service TEXT NOT NULL, 
                  username TEXT NOT NULL, 
                  password TEXT NOT NULL)''')
    conn.commit()
    conn.close()

# Ensure DB exists (in memory or mapped volume)
if not os.path.exists('/data'):
    os.makedirs('/data')
init_db()

@app.route('/')
def index():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM credentials")
    rows = c.fetchall()
    conn.close()
    
    fernet = get_fernet()
    credentials = []
    for row in rows:
        try:
            decrypted_pw = fernet.decrypt(row['password'].encode()).decode()
            credentials.append({
                'id': row['id'],
                'service': row['service'],
                'username': row['username'],
                'password': decrypted_pw
            })
        except Exception as e:
            credentials.append({
                'id': row['id'],
                'service': row['service'],
                'username': row['username'],
                'password': '[Decryption Failed]'
            })
            
    return render_template('index.html', credentials=credentials)

@app.route('/add', methods=['POST'])
def add_credential():
    service = request.form['service']
    username = request.form['username']
    password = request.form['password']
    
    fernet = get_fernet()
    encrypted_pw = fernet.encrypt(password.encode()).decode()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO credentials (service, username, password) VALUES (?, ?, ?)",
              (service, username, encrypted_pw))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['POST'])
def edit_credential(id):
    service = request.form['service']
    username = request.form['username']
    password = request.form['password']
    
    fernet = get_fernet()
    encrypted_pw = fernet.encrypt(password.encode()).decode()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE credentials SET service=?, username=?, password=? WHERE id=?",
              (service, username, encrypted_pw, id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_credential(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM credentials WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
