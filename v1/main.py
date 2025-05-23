from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# --- Data Models (Simulated) ---

managers_db = {}
customers_db = {}
transactions_db = []
next_customer_id = 1
next_transaction_id = 1


# --- Authentication (Basic Example - Replace with proper security) ---

def authenticate_manager(username, password):
    manager = managers_db.get(username)
    if manager and manager['password'] == password:
        return {"username": username}
    return None


def authenticate_customer(email, password):
    for customer_id, customer in customers_db.items():
        if customer['email'] == email and customer['password'] == password:
            return customer_id
    return None


# --- Helper Function for Authentication ---

def require_manager_auth():
    auth = request.headers.get('Authorization')
    if not auth or not auth.startswith('Bearer '):
        return None
    token = auth.split(' ')[1]  # In a real app, you'd validate this token
    # For this example, we'll just extract the username if it's in our dummy db
    for username in managers_db:
        if token == "dummy_manager_token_" + username:
            return {"username": username}
    return None


def require_customer_auth():
    auth = request.headers.get('Authorization')
    if not auth or not auth.startswith('Bearer '):
        return None
    token = auth.split(' ')[1]  # In a real app, you'd validate this token
    # For this example, we'll just extract the customer_id if it's in our dummy scenario
    for customer_id, customer in customers_db.items():
        if token == f"dummy_customer_token_{customer_id}":
            return customer_id
    return None


# --- Manager Endpoints ---

@app.route('/managers/register/', methods=['POST'])
def register_manager():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if username in managers_db:
        return jsonify({"error": "Username already exists"}), 400
    managers_db[username] = {"password": password}
    return jsonify({"message": "Manager registered successfully"}), 201


@app.route('/managers/login/', methods=['POST'])
def login_manager():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    manager = authenticate_manager(username, password)
    if manager:
        return jsonify({"access_token": f"dummy_manager_token_{username}"}), 200  # Dummy token
    return jsonify({"error": "Invalid credentials"}), 401


@app.route('/managers/stats/', methods=['GET'])
def view_system_statistics():
    manager = require_manager_auth()
    if not manager:
        return jsonify({"error": "Unauthorized"}), 401
    total_balance = sum(customer['balance'] for customer in customers_db.values())
    stats = {
        "total_customers": len(customers_db),
        "total_transactions": len(transactions_db),
        "total_balance": total_balance
    }
    return jsonify(stats), 200


@app.route('/managers/customers/', methods=['GET'])
def list_customers():
    manager = require_manager_auth()
    if not manager:
        return jsonify({"error": "Unauthorized"}), 401
    customers_list = [{"account_id": id, "name": customer['name'], "email": customer['email']} for id, customer in
                      customers_db.items()]
    return jsonify(customers_list), 200


@app.route('/managers/customers/search/', methods=['GET'])
def search_customers():
    manager = require_manager_auth()
    if not manager:
        return jsonify({"error": "Unauthorized"}), 401
    name = request.args.get('name')
    email = request.args.get('email')
    account_id_str = request.args.get('account_id')
    account_id = int(account_id_str) if account_id_str else None

    results = []
    for id, customer in customers_db.items():
        if name and name.lower() in customer['name'].lower():
            results.append({"account_id": id, "name": customer['name'], "email": customer['email']})
        elif email and email.lower() == customer['email'].lower():
            results.append({"account_id": id, "name": customer['name'], "email": customer['email']})
        elif account_id and id == account_id:
            results.append({"account_id": id, "name": customer['name'], "email": customer['email']})
    return jsonify(results), 200


@app.route('/managers/customers/<int:customer_id>/transactions/', methods=['GET'])
def view_customer_transactions(customer_id):
    manager = require_manager_auth()
    if not manager:
        return jsonify({"error": "Unauthorized"}), 401
    customer = customers_db.get(customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404
    customer_transactions = [tx for tx in transactions_db if tx['account_id'] == customer_id]
    return jsonify(customer_transactions), 200


@app.route('/managers/transactions/', methods=['GET'])
def view_all_transactions():
    manager = require_manager_auth()
    if not manager:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(transactions_db), 200


@app.route('/managers/logout/', methods=['POST'])
def manager_logout():
    manager = require_manager_auth()
    if not manager:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"message": "Manager logged out"}), 200


# --- Customer Endpoints ---

@app.route('/customers/register/', methods=['POST'])
def register_customer():
    global next_customer_id
    global next_transaction_id
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    initial_deposit = data.get('initial_deposit', 0.0)
    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400
    if any(c['email'] == email for c in customers_db.values()):
        return jsonify({"error": "Email already registered"}), 400
    account_id = next_customer_id
    next_customer_id += 1
    customers_db[account_id] = {
        "name": name,
        "email": email,
        "password": password,
        "balance": initial_deposit
    }
    transactions_db.append({
        "transaction_id": next_transaction_id,
        "account_id": account_id,
        "transaction_type": "deposit",
        "amount": initial_deposit,
        "timestamp": datetime.now().isoformat(),
        "description": "Initial deposit"
    })
    next_transaction_id += 1
    return jsonify({"message": "Customer registered successfully", "account_id": account_id}), 201


@app.route('/customers/login/', methods=['POST'])
def login_customer():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    customer_id = authenticate_customer(email, password)
    if customer_id is not None:
        return jsonify(
            {"access_token": f"dummy_customer_token_{customer_id}", "account_id": customer_id}), 200  # Dummy token
    return jsonify({"error": "Invalid credentials"}), 401


@app.route('/customers/me/balance/', methods=['GET'])
def view_balance():
    customer_id = require_customer_auth()
    if customer_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    customer = customers_db.get(customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404
    return jsonify({"balance": customer['balance']}), 200


@app.route('/customers/me/deposit/', methods=['POST'])
def deposit():
    global next_transaction_id
    customer_id = require_customer_auth()
    if customer_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    amount = data.get('amount')
    if amount is None or amount <= 0:
        return jsonify({"error": "Invalid deposit amount"}), 400
    customer = customers_db.get(customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404
    customer['balance'] += amount
    transactions_db.append({
        "transaction_id": next_transaction_id,
        "account_id": customer_id,
        "transaction_type": "deposit",
        "amount": amount,
        "timestamp": datetime.now().isoformat(),
        "description": "Deposit"
    })
    next_transaction_id += 1
    return jsonify({"message": "Deposit successful", "new_balance": customer['balance']}), 200


@app.route('/customers/me/withdraw/', methods=['POST'])
def withdraw():
    global next_transaction_id
    customer_id = require_customer_auth()
    if customer_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    amount = data.get('amount')
    if amount is None or amount <= 0:
        return jsonify({"error": "Invalid withdrawal amount"}), 400
    customer = customers_db.get(customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404
    if customer['balance'] < amount:
        return jsonify({"error": "Insufficient funds"}), 400
    customer['balance'] -= amount
    transactions_db.append({
        "transaction_id": next_transaction_id,
        "account_id": customer_id,
        "transaction_type": "withdrawal",
        "amount": amount,
        "timestamp": datetime.now().isoformat(),
        "description": "Withdrawal"
    })
    next_transaction_id += 1
    return jsonify({"message": "Withdrawal successful", "new_balance": customer['balance']}), 200


@app.route('/customers/me/transfer/', methods=['POST'])
def transfer():
    global next_transaction_id
    customer_id = require_customer_auth()
    if customer_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    recipient_account_id = data.get('recipient_account_id')
    amount = data.get('amount')
    if recipient_account_id is None or amount is None or amount <= 0:
        return jsonify({"error": "Recipient account ID and a valid amount are required"}), 400
    if recipient_account_id == customer_id:
        return jsonify({"error": "Cannot transfer to your own account"}), 400

    sender = customers_db.get(customer_id)
    recipient = customers_db.get(recipient_account_id)

    if not sender:
        return jsonify({"error": "Sender account not found"}), 404
    if not recipient:
        return jsonify({"error": "Recipient account not found"}), 404
    if sender['balance'] < amount:
        return jsonify({"error": "Insufficient funds"}), 400

    sender['balance'] -= amount
    recipient['balance'] += amount

    transactions_db.append({
        "transaction_id": next_transaction_id,
        "account_id": customer_id,
        "transaction_type": "transfer_out",
        "amount": amount,
        "timestamp": datetime.now().isoformat(),
        "description": f"Transfer to account {recipient_account_id}"
    })
    next_transaction_id += 1
    transactions_db.append({
        "transaction_id": next_transaction_id,
        "account_id": recipient_account_id,
        "transaction_type": "transfer_in",
        "amount": amount,
        "timestamp": datetime.now().isoformat(),
        "description": f"Transfer from account {customer_id}"
    })
    next_transaction_id += 1
    return jsonify({"message": f"Transfer of {amount} successful to account {recipient_account_id}",
                    "new_balance": sender['balance']}), 200


@app.route('/customers/me/transactions/', methods=['GET'])
def view_transaction_history():
    customer_id = require_customer_auth()
    if customer_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    customer_transactions = [tx for tx in transactions_db if tx['account_id'] == customer_id]
    return jsonify(customer_transactions), 200


@app.route('/customers/me/transactions/filter/', methods=['GET'])
def filter_transactions():
    customer_id = require_customer_auth()
    if customer_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    transaction_type = request.args.get('transaction_type')

    filtered_transactions = [tx for tx in transactions_db if tx['account_id'] == customer_id]

    if start_date_str:
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        filtered_transactions = [tx for tx in filtered_transactions if
                                 datetime.fromisoformat(tx['timestamp'].replace('Z', '+00:00')) >= start_date]
    if end_date_str:
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        filtered_transactions = [tx for tx in filtered_transactions if
                                 datetime.fromisoformat(tx['timestamp'].replace('Z', '+00:00')) <= end_date]
    if transaction_type:
        filtered_transactions = [tx for tx in filtered_transactions if tx['transaction_type'] == transaction_type]

    return jsonify(filtered_transactions), 200


@app.route('/customers/me/transactions/search/', methods=['GET'])
def search_transactions():
    customer_id = require_customer_auth()
    if customer_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    description = request.args.get('description', '').lower()
    searched_transactions = [
        tx for tx in transactions_db
        if tx['account_id'] == customer_id and description in (tx.get('description', '').lower())
    ]
    return jsonify(searched_transactions), 200


@app.route('/customers/logout/', methods=['POST'])
def customer_logout():
    customer_id = require_customer_auth()
    if customer_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"message": "Customer logged out"}), 200


if __name__ == '__main__':
    app.run(debug=True)
