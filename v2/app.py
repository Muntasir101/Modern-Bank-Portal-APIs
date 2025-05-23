from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
import secrets
from functools import wraps

app = Flask(__name__)
DATABASE = 'bank.db'
SECRET_KEY = 'your_secret_key_here'  # Replace with a strong, random key
app.config['SECRET_KEY'] = SECRET_KEY

first_request = True


# --- Database Initialization ---

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS managers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                auth_token TEXT UNIQUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                balance REAL NOT NULL DEFAULT 0.0,
                auth_token TEXT UNIQUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp DATETIME NOT NULL,
                description TEXT,
                FOREIGN KEY (account_id) REFERENCES customers (account_id)
            )
        ''')
        conn.commit()


@app.before_request
def before_request():
    global first_request
    if first_request:
        init_db()
        first_request = False


# ... rest of your code ...


# --- Database Helper Functions ---

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def close_db(conn):
    if conn:
        conn.close()


# --- Authentication Decorators ---

def token_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Token is missing'}), 401
            token = auth_header.split(' ')[1]
            conn = get_db()
            cursor = conn.cursor()
            user = None
            if role == 'manager':
                cursor.execute("SELECT * FROM managers WHERE auth_token = ?", (token,))
                manager = cursor.fetchone()
                if manager:
                    user = dict(manager)
            elif role == 'customer':
                cursor.execute("SELECT * FROM customers WHERE auth_token = ?", (token,))
                customer = cursor.fetchone()
                if customer:
                    user = dict(customer)
                    kwargs['current_customer_id'] = user['account_id']
            close_db(conn)
            if not user:
                return jsonify({'error': 'Invalid or expired token'}), 401
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# --- Manager Endpoints ---

@app.route('/managers/register/', methods=['POST'])
def register_manager():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    conn = get_db()
    cursor = conn.cursor()
    if cursor.execute("SELECT * FROM managers WHERE username = ?", (username,)).fetchone():
        close_db(conn)
        return jsonify({'error': 'Username already exists'}), 400
    cursor.execute("INSERT INTO managers (username, password) VALUES (?, ?)",
                   (username, password))  # In real app, hash password
    conn.commit()
    close_db(conn)
    return jsonify({'message': 'Manager registered successfully'}), 201


@app.route('/managers/login/', methods=['POST'])
def login_manager():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    conn = get_db()
    cursor = conn.cursor()
    manager = cursor.execute("SELECT * FROM managers WHERE username = ? AND password = ?",
                             (username, password)).fetchone()  # In real app, compare hashed password
    if manager:
        auth_token = secrets.token_hex(32)
        cursor.execute("UPDATE managers SET auth_token = ? WHERE id = ?", (auth_token, manager['id']))
        conn.commit()
        close_db(conn)
        return jsonify({'access_token': auth_token}), 200
    close_db(conn)
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/managers/stats/', methods=['GET'])
@token_required('manager')
def view_system_statistics():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM customers")
    total_customers = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM transactions")
    total_transactions = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(balance) FROM customers")
    total_balance = cursor.fetchone()[0] or 0.0
    close_db(conn)
    return jsonify({
        'total_customers': total_customers,
        'total_transactions': total_transactions,
        'total_balance': total_balance
    }), 200


@app.route('/managers/customers/', methods=['GET'])
@token_required('manager')
def list_customers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT account_id, name, email FROM customers")
    customers = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(customers), 200


@app.route('/managers/customers/search/', methods=['GET'])
@token_required('manager')
def search_customers():
    name = request.args.get('name')
    email = request.args.get('email')
    account_id_str = request.args.get('account_id')
    account_id = int(account_id_str) if account_id_str else None
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT account_id, name, email FROM customers WHERE 1=1"
    params = []
    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")
    if email:
        query += " AND email = ?"
        params.append(email)
    if account_id:
        query += " AND account_id = ?"
        params.append(account_id)
    cursor.execute(query, params)
    customers = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(customers), 200


@app.route('/managers/customers/<int:customer_id>/transactions/', methods=['GET'])
@token_required('manager')
def view_customer_transactions(customer_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE account_id = ?", (customer_id,))
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/managers/transactions/', methods=['GET'])
@token_required('manager')
def view_all_transactions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions")
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/managers/logout/', methods=['POST'])
@token_required('manager')
def manager_logout():
    auth_token = request.headers.get('Authorization').split(' ')[1]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE managers SET auth_token = NULL WHERE auth_token = ?", (auth_token,))
    conn.commit()
    close_db(conn)
    return jsonify({'message': 'Manager logged out'}), 200


# --- Customer Endpoints ---

@app.route('/customers/register/', methods=['POST'])
def register_customer():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    initial_deposit = data.get('initial_deposit', 0.0)
    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required'}), 400
    conn = get_db()
    cursor = conn.cursor()
    if cursor.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone():
        close_db(conn)
        return jsonify({'error': 'Email already registered'}), 400
    cursor.execute("INSERT INTO customers (name, email, password, balance) VALUES (?, ?, ?, ?)",
                   (name, email, password, initial_deposit))  # In real app, hash password
    account_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO transactions (account_id, transaction_type, amount, timestamp, description) VALUES (?, ?, ?, ?, ?)",
        (account_id, 'deposit', initial_deposit, datetime.now(), 'Initial deposit'))
    conn.commit()
    close_db(conn)
    return jsonify({'message': 'Customer registered successfully', 'account_id': account_id}), 201


@app.route('/customers/login/', methods=['POST'])
def login_customer():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    conn = get_db()
    cursor = conn.cursor()
    customer = cursor.execute("SELECT * FROM customers WHERE email = ? AND password = ?",
                              (email, password)).fetchone()  # In real app, compare hashed password
    if customer:
        auth_token = secrets.token_hex(32)
        cursor.execute("UPDATE customers SET auth_token = ? WHERE account_id = ?", (auth_token, customer['account_id']))
        conn.commit()
        close_db(conn)
        return jsonify({'access_token': auth_token, 'account_id': customer['account_id']}), 200
    close_db(conn)
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/customers/me/balance/', methods=['GET'])
@token_required('customer')
def view_balance(current_customer_id):
    conn = get_db()
    cursor = conn.cursor()
    customer = cursor.execute("SELECT balance FROM customers WHERE account_id = ?", (current_customer_id,)).fetchone()
    close_db(conn)
    if customer:
        return jsonify({'balance': customer['balance']}), 200
    return jsonify({'error': 'Customer not found'}), 404


@app.route('/customers/me/deposit/', methods=['POST'])
@token_required('customer')
def deposit(current_customer_id):
    data = request.get_json()
    amount = data.get('amount')
    if amount is None or amount <= 0:
        return jsonify({'error': 'Invalid deposit amount'}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE customers SET balance = balance + ? WHERE account_id = ?", (amount, current_customer_id))
        cursor.execute("INSERT INTO transactions (account_id, transaction_type, amount, timestamp, description) "
                       "VALUES (?, ?, ?, ?, ?)",
                       (current_customer_id, 'deposit', amount, datetime.now(), 'Deposit'))
        conn.commit()
        cursor.execute("SELECT balance FROM customers WHERE account_id = ?", (current_customer_id,))
        new_balance = cursor.fetchone()[0]
        return jsonify({'message': 'Deposit successful', 'new_balance': new_balance}), 200
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        close_db(conn)


@app.route('/customers/me/withdraw/', methods=['POST'])
@token_required('customer')
def withdraw(current_customer_id):
    data = request.get_json()
    amount = data.get('amount')
    if amount is None or amount <= 0:
        return jsonify({'error': 'Invalid withdrawal amount'}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT balance FROM customers WHERE account_id = ?", (current_customer_id,))
        current_balance = cursor.fetchone()[0]
        if current_balance < amount:
            return jsonify({'error': 'Insufficient funds'}), 400
        cursor.execute("UPDATE customers SET balance = balance - ? WHERE account_id = ?", (amount, current_customer_id))
        cursor.execute(
            "INSERT INTO transactions (account_id, transaction_type, amount, timestamp, description) VALUES (?, ?, ?, ?, ?)",
            (current_customer_id, 'withdrawal', amount, datetime.now(), 'Withdrawal'))
        conn.commit()
        cursor.execute("SELECT balance FROM customers WHERE account_id = ?", (current_customer_id,))
        new_balance = cursor.fetchone()[0]
        return jsonify({'message': 'Withdrawal successful', 'new_balance': new_balance}), 200
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        close_db(conn)


@app.route('/customers/me/transfer/', methods=['POST'])
@token_required('customer')
def transfer(current_customer_id):
    data = request.get_json()
    recipient_account_id = data.get('recipient_account_id')
    amount = data.get('amount')
    if recipient_account_id is None or amount is None or amount <= 0:
        return jsonify({'error': 'Recipient account ID and a valid amount are required'}), 400
    if recipient_account_id == current_customer_id:
        return jsonify({'error': 'Cannot transfer to your own account'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT balance FROM customers WHERE account_id = ?", (current_customer_id,))
        sender_balance = cursor.fetchone()[0]
        if sender_balance < amount:
            return jsonify({'error': 'Insufficient funds'}), 400

        cursor.execute("SELECT * FROM customers WHERE account_id = ?", (recipient_account_id,))
        recipient = cursor.fetchone()
        if not recipient:
            return jsonify({'error': 'Recipient account not found'}), 404

        cursor.execute("UPDATE customers SET balance = balance - ? WHERE account_id = ?", (amount, current_customer_id))
        cursor.execute("UPDATE customers SET balance = balance + ? WHERE account_id = ?",
                       (amount, recipient_account_id))
        cursor.execute(
            "INSERT INTO transactions (account_id, transaction_type, amount, timestamp, description) VALUES (?, ?, ?, ?, ?)",
            (
            current_customer_id, 'transfer_out', amount, datetime.now(), f'Transfer to account {recipient_account_id}'))
        cursor.execute(
            "INSERT INTO transactions (account_id, transaction_type, amount, timestamp, description) VALUES (?, ?, ?, ?, ?)",
            (recipient_account_id, 'transfer_in', amount, datetime.now(),
             f'Transfer from account {current_customer_id}'))
        conn.commit()
        cursor.execute("SELECT balance FROM customers WHERE account_id = ?", (current_customer_id,))
        new_balance = cursor.fetchone()[0]
        return jsonify({'message': f'Transfer of {amount} successful to account {recipient_account_id}',
                        'new_balance': new_balance}), 200
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        close_db(conn)


@app.route('/customers/me/transactions/', methods=['GET'])
@token_required('customer')
def view_transaction_history(current_customer_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE account_id = ? ORDER BY timestamp DESC", (current_customer_id,))
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/customers/me/transactions/filter/', methods=['GET'])
@token_required('customer')
def filter_transactions(current_customer_id):
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    transaction_type = request.args.get('transaction_type')

    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM transactions WHERE account_id = ?"
    params = [current_customer_id]

    if start_date_str:
        query += " AND timestamp >= ?"
        params.append(start_date_str)
    if end_date_str:
        query += " AND timestamp <= ?"
        params.append(end_date_str)
    if transaction_type:
        query += " AND transaction_type = ?"
        params.append(transaction_type)

    query += " ORDER BY timestamp DESC"
    cursor.execute(query, params)
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/customers/me/transactions/search/', methods=['GET'])
@token_required('customer')
def search_transactions(current_customer_id):
    description = request.args.get('description', '').lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE account_id = ? AND LOWER(description) LIKE ? ORDER BY timestamp "
                   "DESC",
                   (current_customer_id, f"%{description}%"))
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/customers/logout/', methods=['POST'])
@token_required('customer')
def customer_logout(current_customer_id):
    auth_token = request.headers.get('Authorization').split(' ')[1]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE customers SET auth_token = NULL WHERE auth_token = ?", (auth_token,))
    conn.commit()
    close_db(conn)
    return jsonify({'message': 'Customer logged out'}), 200


if __name__ == '__main__':
    app.run(debug=True)


@app.route('/customers/me/transactions/filter/', methods=['GET'])
@token_required('customer')
def filter_transactions(current_customer_id):
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    transaction_type = request.args.get('transaction_type')

    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM transactions WHERE account_id = ?"
    params = [current_customer_id]

    if start_date_str:
        query += " AND timestamp >= ?"
        params.append(start_date_str)
    if end_date_str:
        query += " AND timestamp <= ?"
        params

    params.append(end_date_str)
    if transaction_type:
        query += " AND transaction_type = ?"
        params.append(transaction_type)

    query += " ORDER BY timestamp DESC"
    cursor.execute(query, params)
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/customers/me/transactions/search/', methods=['GET'])
@token_required('customer')
def search_transactions(current_customer_id):
    description = request.args.get('description', '').lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transactions WHERE account_id = ? AND LOWER(description) LIKE ? ORDER BY timestamp DESC",
        (current_customer_id, f"%{description}%"))
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/customers/logout/', methods=['POST'])
@token_required('customer')
def customer_logout(current_customer_id):
    auth_token = request.headers.get('Authorization').split(' ')[1]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE customers SET auth_token = NULL WHERE auth_token = ?", (auth_token,))
    conn.commit()
    close_db(conn)
    return jsonify({'message': 'Customer logged out'}), 200


if __name__ == '__main__':
    app.run(debug=True)
