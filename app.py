"""
for Swagger:
http://127.0.0.1:5000/apidocs/
"""

from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
import secrets
from functools import wraps
from flasgger import Swagger, swag_from  # Import Swagger and swag_from

app = Flask(__name__)
DATABASE = 'bank.db'
SECRET_KEY = 'your_secret_key_here'  # Replace with a strong, random key
app.config['SECRET_KEY'] = SECRET_KEY

# --- Swagger Configuration ---
# Basic Swagger UI setup
app.config['SWAGGER'] = {
    'title': 'Banking API',
    'uiversion': 3,
    'version': '1.0.0',
    'description': 'API for a simple banking system with manager and customer functionalities.',
    'termsOfService': 'http://example.com/terms',
    'contact': {
        'name': 'API Support',
        'url': 'http://example.com/support',
        'email': 'support@example.com'
    },
    'license': {
        'name': 'Apache 2.0',
        'url': 'http://www.apache.org/licenses/LICENSE-2.0.html'
    },
    'specs_route': '/apidocs/'  # URL to access Swagger UI
}

# Define security schemes for Swagger (Bearer Token for JWT)
swagger_config = Swagger.DEFAULT_CONFIG
swagger_config['securityDefinitions'] = {
    "BearerAuth": {
        "type": "apiKey",
        "name": "Authorization",
        "in": "header",
        "description": "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
    }
}
swagger = Swagger(app, config=swagger_config)  # Initialize Flasgger

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
def before_request_func():  # Renamed to avoid conflict with flask.before_request
    global first_request
    if first_request:
        init_db()
        first_request = False


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
@swag_from({
    'tags': ['Manager Authentication'],
    'summary': 'Register a new bank manager.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'example': 'admin_user'},
                    'password': {'type': 'string', 'example': 'securepassword123'}
                },
                'required': ['username', 'password']
            }
        }
    ],
    'responses': {
        201: {
            'description': 'Manager registered successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'}
                }
            }
        },
        400: {
            'description': 'Username and password are required or Username already exists.',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    }
})
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
@swag_from({
    'tags': ['Manager Authentication'],
    'summary': 'Login for a bank manager.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'example': 'admin_user'},
                    'password': {'type': 'string', 'example': 'securepassword123'}
                },
                'required': ['username', 'password']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Login successful, returns access token.',
            'schema': {
                'type': 'object',
                'properties': {
                    'access_token': {'type': 'string'}
                }
            }
        },
        400: {'description': 'Username and password are required.'},
        401: {'description': 'Invalid credentials.'}
    }
})
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
@swag_from({
    'tags': ['Manager Operations'],
    'summary': 'View system-wide statistics.',
    'security': [{"BearerAuth": []}],
    'responses': {
        200: {
            'description': 'System statistics.',
            'schema': {
                'type': 'object',
                'properties': {
                    'total_customers': {'type': 'integer'},
                    'total_transactions': {'type': 'integer'},
                    'total_balance': {'type': 'number', 'format': 'float'}
                }
            }
        },
        401: {'description': 'Token is missing or invalid.'}
    }
})
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
@swag_from({
    'tags': ['Manager Operations'],
    'summary': 'List all customers.',
    'security': [{"BearerAuth": []}],
    'responses': {
        200: {
            'description': 'A list of customers.',
            'schema': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'account_id': {'type': 'integer'},
                        'name': {'type': 'string'},
                        'email': {'type': 'string', 'format': 'email'}
                    }
                }
            }
        },
        401: {'description': 'Token is missing or invalid.'}
    }
})
def list_customers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT account_id, name, email FROM customers")
    customers = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(customers), 200


@app.route('/managers/customers/search/', methods=['GET'])
@token_required('manager')
@swag_from({
    'tags': ['Manager Operations'],
    'summary': 'Search for customers by name, email, or account ID.',
    'security': [{"BearerAuth": []}],
    'parameters': [
        {
            'name': 'name',
            'in': 'query',
            'type': 'string',
            'required': False,
            'description': 'Part of customer name to search for.'
        },
        {
            'name': 'email',
            'in': 'query',
            'type': 'string',
            'format': 'email',
            'required': False,
            'description': 'Exact customer email to search for.'
        },
        {
            'name': 'account_id',
            'in': 'query',
            'type': 'integer',
            'required': False,
            'description': 'Exact customer account ID to search for.'
        }
    ],
    'responses': {
        200: {
            'description': 'A list of matching customers.',
            'schema': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'account_id': {'type': 'integer'},
                        'name': {'type': 'string'},
                        'email': {'type': 'string', 'format': 'email'}
                    }
                }
            }
        },
        401: {'description': 'Token is missing or invalid.'}
    }
})
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
@swag_from({
    'tags': ['Manager Operations'],
    'summary': "View a specific customer's transaction history.",
    'security': [{"BearerAuth": []}],
    'parameters': [
        {
            'name': 'customer_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': "The ID of the customer whose transactions to view."
        }
    ],
    'responses': {
        200: {
            'description': "A list of the customer's transactions.",
            'schema': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'transaction_id': {'type': 'integer'},
                        'account_id': {'type': 'integer'},
                        'transaction_type': {'type': 'string',
                                             'enum': ['deposit', 'withdrawal', 'transfer_in', 'transfer_out']},
                        'amount': {'type': 'number', 'format': 'float'},
                        'timestamp': {'type': 'string', 'format': 'date-time'},
                        'description': {'type': 'string'}
                    }
                }
            }
        },
        401: {'description': 'Token is missing or invalid.'}
    }
})
def view_customer_transactions(customer_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE account_id = ?", (customer_id,))
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/managers/transactions/', methods=['GET'])
@token_required('manager')
@swag_from({
    'tags': ['Manager Operations'],
    'summary': 'View all transactions in the system.',
    'security': [{"BearerAuth": []}],
    'responses': {
        200: {
            'description': 'A list of all transactions.',
            'schema': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'transaction_id': {'type': 'integer'},
                        'account_id': {'type': 'integer'},
                        'transaction_type': {'type': 'string',
                                             'enum': ['deposit', 'withdrawal', 'transfer_in', 'transfer_out',
                                                      'Initial deposit']},
                        'amount': {'type': 'number', 'format': 'float'},
                        'timestamp': {'type': 'string', 'format': 'date-time'},
                        'description': {'type': 'string'}
                    }
                }
            }
        },
        401: {'description': 'Token is missing or invalid.'}
    }
})
def view_all_transactions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions")
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/managers/logout/', methods=['POST'])
@token_required('manager')
@swag_from({
    'tags': ['Manager Authentication'],
    'summary': 'Logout for a bank manager.',
    'security': [{"BearerAuth": []}],
    'responses': {
        200: {'description': 'Manager logged out successfully.'},
        401: {'description': 'Token is missing or invalid.'}
    }
})
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
@swag_from({
    'tags': ['Customer Authentication'],
    'summary': 'Register a new customer.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'example': 'John Doe'},
                    'email': {'type': 'string', 'format': 'email', 'example': 'john.doe@example.com'},
                    'password': {'type': 'string', 'example': 'password123'},
                    'initial_deposit': {'type': 'number', 'format': 'float', 'example': 100.50, 'default': 0.0}
                },
                'required': ['name', 'email', 'password']
            }
        }
    ],
    'responses': {
        201: {
            'description': 'Customer registered successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'account_id': {'type': 'integer'}
                }
            }
        },
        400: {'description': 'Required fields missing or email already registered.'}
    }
})
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
    if initial_deposit > 0:  # Only record initial deposit if it's greater than 0
        cursor.execute(
            "INSERT INTO transactions (account_id, transaction_type, amount, timestamp, description) VALUES (?, ?, ?, ?, ?)",
            (account_id, 'deposit', initial_deposit, datetime.now(), 'Initial deposit'))
    conn.commit()
    close_db(conn)
    return jsonify({'message': 'Customer registered successfully', 'account_id': account_id}), 201


@app.route('/customers/login/', methods=['POST'])
@swag_from({
    'tags': ['Customer Authentication'],
    'summary': 'Login for a customer.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'format': 'email', 'example': 'john.doe@example.com'},
                    'password': {'type': 'string', 'example': 'password123'}
                },
                'required': ['email', 'password']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Login successful, returns access token and account ID.',
            'schema': {
                'type': 'object',
                'properties': {
                    'access_token': {'type': 'string'},
                    'account_id': {'type': 'integer'}
                }
            }
        },
        400: {'description': 'Email and password are required.'},
        401: {'description': 'Invalid credentials.'}
    }
})
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
@swag_from({
    'tags': ['Customer Account'],
    'summary': 'View current account balance.',
    'security': [{"BearerAuth": []}],
    'responses': {
        200: {
            'description': 'Current account balance.',
            'schema': {
                'type': 'object',
                'properties': {
                    'balance': {'type': 'number', 'format': 'float'}
                }
            }
        },
        401: {'description': 'Token is missing or invalid.'},
        404: {'description': 'Customer not found.'}
    }
})
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
@swag_from({
    'tags': ['Customer Account'],
    'summary': 'Deposit funds into account.',
    'security': [{"BearerAuth": []}],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'amount': {'type': 'number', 'format': 'float', 'example': 50.25,
                               'description': 'Amount to deposit, must be positive.'}
                },
                'required': ['amount']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Deposit successful.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'new_balance': {'type': 'number', 'format': 'float'}
                }
            }
        },
        400: {'description': 'Invalid deposit amount.'},
        401: {'description': 'Token is missing or invalid.'},
        500: {'description': 'Database error.'}
    }
})
def deposit(current_customer_id):
    data = request.get_json()
    amount = data.get('amount')
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:  # Added type check
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
@swag_from({
    'tags': ['Customer Account'],
    'summary': 'Withdraw funds from account.',
    'security': [{"BearerAuth": []}],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'amount': {'type': 'number', 'format': 'float', 'example': 20.00,
                               'description': 'Amount to withdraw, must be positive.'}
                },
                'required': ['amount']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Withdrawal successful.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'new_balance': {'type': 'number', 'format': 'float'}
                }
            }
        },
        400: {'description': 'Invalid withdrawal amount or insufficient funds.'},
        401: {'description': 'Token is missing or invalid.'},
        500: {'description': 'Database error.'}
    }
})
def withdraw(current_customer_id):
    data = request.get_json()
    amount = data.get('amount')
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:  # Added type check
        return jsonify({'error': 'Invalid withdrawal amount'}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT balance FROM customers WHERE account_id = ?", (current_customer_id,))
        current_balance_row = cursor.fetchone()
        if not current_balance_row:  # Should not happen due to token_required, but good practice
            return jsonify({'error': 'Customer not found'}), 404
        current_balance = current_balance_row[0]

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
@swag_from({
    'tags': ['Customer Account'],
    'summary': 'Transfer funds to another customer account.',
    'security': [{"BearerAuth": []}],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'recipient_account_id': {'type': 'integer', 'example': 2,
                                             'description': 'Account ID of the recipient.'},
                    'amount': {'type': 'number', 'format': 'float', 'example': 25.75,
                               'description': 'Amount to transfer, must be positive.'}
                },
                'required': ['recipient_account_id', 'amount']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Transfer successful.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'new_balance': {'type': 'number', 'format': 'float'}
                }
            }
        },
        400: {
            'description': 'Invalid request (missing fields, invalid amount, transfer to own account, insufficient funds).'},
        401: {'description': 'Token is missing or invalid.'},
        404: {'description': 'Recipient account not found.'},
        500: {'description': 'Database error.'}
    }
})
def transfer(current_customer_id):
    data = request.get_json()
    recipient_account_id = data.get('recipient_account_id')
    amount = data.get('amount')
    if recipient_account_id is None or amount is None or not isinstance(amount, (
    int, float)) or amount <= 0:  # Added type check
        return jsonify({'error': 'Recipient account ID and a valid amount are required'}), 400
    if recipient_account_id == current_customer_id:
        return jsonify({'error': 'Cannot transfer to your own account'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT balance FROM customers WHERE account_id = ?", (current_customer_id,))
        sender_balance_row = cursor.fetchone()
        if not sender_balance_row:  # Should not happen
            return jsonify({'error': 'Sender account not found'}), 404  # Should be caught by token_required
        sender_balance = sender_balance_row[0]

        if sender_balance < amount:
            return jsonify({'error': 'Insufficient funds'}), 400

        cursor.execute("SELECT account_id FROM customers WHERE account_id = ?",
                       (recipient_account_id,))  # Check only for existence
        recipient = cursor.fetchone()
        if not recipient:
            return jsonify({'error': 'Recipient account not found'}), 404

        # Perform transactions
        cursor.execute("UPDATE customers SET balance = balance - ? WHERE account_id = ?", (amount, current_customer_id))
        cursor.execute("UPDATE customers SET balance = balance + ? WHERE account_id = ?",
                       (amount, recipient_account_id))
        timestamp = datetime.now()
        cursor.execute(
            "INSERT INTO transactions (account_id, transaction_type, amount, timestamp, description) VALUES (?, ?, ?, ?, ?)",
            (current_customer_id, 'transfer_out', amount, timestamp, f'Transfer to account {recipient_account_id}'))
        cursor.execute(
            "INSERT INTO transactions (account_id, transaction_type, amount, timestamp, description) VALUES (?, ?, ?, ?, ?)",
            (recipient_account_id, 'transfer_in', amount, timestamp, f'Transfer from account {current_customer_id}'))
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
@swag_from({
    'tags': ['Customer Transactions'],
    'summary': 'View own transaction history.',
    'security': [{"BearerAuth": []}],
    'responses': {
        200: {
            'description': 'A list of own transactions, ordered by most recent first.',
            'schema': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'transaction_id': {'type': 'integer'},
                        'account_id': {'type': 'integer'},
                        'transaction_type': {'type': 'string'},
                        'amount': {'type': 'number', 'format': 'float'},
                        'timestamp': {'type': 'string', 'format': 'date-time'},
                        'description': {'type': 'string'}
                    }
                }
            }
        },
        401: {'description': 'Token is missing or invalid.'}
    }
})
def view_transaction_history(current_customer_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE account_id = ? ORDER BY timestamp DESC", (current_customer_id,))
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/customers/me/transactions/filter/', methods=['GET'])
@token_required('customer')
@swag_from({
    'tags': ['Customer Transactions'],
    'summary': 'Filter own transactions by date range and/or type.',
    'security': [{"BearerAuth": []}],
    'parameters': [
        {
            'name': 'start_date',
            'in': 'query',
            'type': 'string',
            'format': 'date',  # YYYY-MM-DD
            'required': False,
            'description': 'Start date for filtering (YYYY-MM-DD).'
        },
        {
            'name': 'end_date',
            'in': 'query',
            'type': 'string',
            'format': 'date',  # YYYY-MM-DD
            'required': False,
            'description': 'End date for filtering (YYYY-MM-DD). Add T23:59:59 for full day.'
        },
        {
            'name': 'transaction_type',
            'in': 'query',
            'type': 'string',
            'enum': ['deposit', 'withdrawal', 'transfer_in', 'transfer_out', 'Initial deposit'],
            'required': False,
            'description': 'Type of transaction to filter by.'
        }
    ],
    'responses': {
        200: {'description': 'A list of filtered transactions.'},  # Schema same as /me/transactions/
        401: {'description': 'Token is missing or invalid.'}
    }
})
def filter_transactions(current_customer_id):
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    transaction_type = request.args.get('transaction_type')

    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM transactions WHERE account_id = ?"
    params = [current_customer_id]

    if start_date_str:
        try:
            datetime.strptime(start_date_str, '%Y-%m-%d')  # Validate date format
            query += " AND DATE(timestamp) >= DATE(?)"  # Compare dates
            params.append(start_date_str)
        except ValueError:
            return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD.'}), 400

    if end_date_str:
        try:
            datetime.strptime(end_date_str, '%Y-%m-%d')  # Validate date format
            query += " AND DATE(timestamp) <= DATE(?)"  # Compare dates
            params.append(end_date_str)
        except ValueError:
            return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD.'}), 400

    if transaction_type:
        valid_types = ['deposit', 'withdrawal', 'transfer_in', 'transfer_out', 'Initial deposit']
        if transaction_type not in valid_types:
            return jsonify({'error': f'Invalid transaction_type. Must be one of {valid_types}'}), 400
        query += " AND transaction_type = ?"
        params.append(transaction_type)

    query += " ORDER BY timestamp DESC"
    cursor.execute(query, params)
    transactions = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(transactions), 200


@app.route('/customers/me/transactions/search/', methods=['GET'])
@token_required('customer')
@swag_from({
    'tags': ['Customer Transactions'],
    'summary': 'Search own transactions by description.',
    'security': [{"BearerAuth": []}],
    'parameters': [
        {
            'name': 'description',
            'in': 'query',
            'type': 'string',
            'required': True,
            'description': 'Text to search for in transaction descriptions (case-insensitive).'
        }
    ],
    'responses': {
        200: {'description': 'A list of matching transactions.'},  # Schema same as /me/transactions/
        401: {'description': 'Token is missing or invalid.'}
    }
})
def search_transactions(current_customer_id):
    description = request.args.get('description')
    if not description:  # Ensure description is provided
        return jsonify({'error': 'Description query parameter is required'}), 400
    description = description.lower()
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
@swag_from({
    'tags': ['Customer Authentication'],
    'summary': 'Logout for a customer.',
    'security': [{"BearerAuth": []}],
    'responses': {
        200: {'description': 'Customer logged out successfully.'},
        401: {'description': 'Token is missing or invalid.'}
    }
})
def customer_logout(
        current_customer_id):  # current_customer_id is injected by token_required but not directly used here
    auth_token = request.headers.get('Authorization').split(' ')[1]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE customers SET auth_token = NULL WHERE auth_token = ?", (auth_token,))
    conn.commit()
    close_db(conn)
    return jsonify({'message': 'Customer logged out'}), 200


# Removed duplicate route definitions that were at the end of your original script

if __name__ == '__main__':
    # init_db() # Initialize DB when script runs directly, or rely on before_request
    app.run(debug=True)
