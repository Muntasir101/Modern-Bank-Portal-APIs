
# Banking API

A simple RESTful API for a banking system built with Flask, providing functionalities for both bank managers and customers. It uses SQLite for data storage and Flasgger for API documentation.

## Table of Contents

- [Features](#features)
  - [Manager Features](#manager-features)
  - [Customer Features](#customer-features)
- [Technologies Used](#technologies-used)
- [Prerequisites](#prerequisites)
- [Setup and Installation](#setup-and-installation)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Database Schema](#database-schema)
  - [managers](#managers)
  - [customers](#customers)
  - [transactions](#transactions)
- [Authentication](#authentication)
- [Project Structure](#project-structure)
- [Future Improvements](#future-improvements)
- [License](#license)

## Features

### Manager Features

- **Register & Login:** Secure registration and login for bank managers.
- **System Statistics:** View overall system statistics including:
    - Total number of customers.
    - Total number of transactions.
    - Total balance across all customer accounts.
- **Customer Management:**
    - List all registered customers.
    - Search for customers by name, email, or account ID.
    - View transaction history for a specific customer.
- **Transaction Oversight:** View all transactions that have occurred in the system.
- **Logout:** Securely log out of the manager session.

### Customer Features

- **Register & Login:** Secure registration and login for customers.
    - Option for an initial deposit upon registration.
- **Account Management:**
    - View current account balance.
    - Deposit funds into their account.
    - Withdraw funds from their account (checks for sufficient balance).
    - Transfer funds to another customer's account (checks for sufficient balance and valid recipient).
- **Transaction History:**
    - View their own transaction history, ordered by most recent.
    - Filter transactions by date range and/or transaction type.
    - Search transactions by keywords in the description.
- **Logout:** Securely log out of the customer session.

## Technologies Used

- **Backend:** Python, Flask
- **Database:** SQLite 3
- **API Documentation:** Flasgger (Swagger UI)
- **Authentication:** Token-based (Bearer Tokens)

## Prerequisites

- Python 3.7+
- pip (Python package installer)

## Setup and Installation

1.  **Clone the repository (if applicable) or download the project files.**
    ```bash
    # If you have it in a git repository
    # git clone <repository-url>
    # cd <project-directory>
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    ```
    Activate the virtual environment:
    -   Windows:
        ```bash
        .\venv\Scripts\activate
        ```
    -   macOS/Linux:
        ```bash
        source venv/bin/activate
        ```

3.  **Install the required Python packages:**
    Create a `requirements.txt` file with the following content:
    ```txt
    Flask
    Flasgger
    ```
    Then run:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

1.  **Ensure your virtual environment is activated.**
2.  **Run the Flask application:**
    Assuming your main Python file is named `app.py` (as is common, or adjust to your filename):
    ```bash
    python app.py
    ```
3.  The application will typically start on `http://127.0.0.1:5000/`.

## API Documentation

The API is documented using Swagger UI, provided by Flasgger. Once the application is running, you can access the interactive API documentation at:

**`http://127.0.0.1:5000/apidocs/`**
**`https://app.swaggerhub.com/apis/MUNTASIR_2/Modern_Bank_API/1.0.0`**

This interface allows you to:
- View all available API endpoints.
- See details about request parameters, request bodies, and response schemas.
- Test the API endpoints directly from your browser.

## Database Schema

The application uses an SQLite database named `bank.db` which is created automatically when the application first starts. It contains the following tables:

### `managers`

| Column     | Type          | Constraints                     | Description                   |
| :--------- | :------------ | :------------------------------ | :---------------------------- |
| `id`       | `INTEGER`     | `PRIMARY KEY AUTOINCREMENT`     | Unique ID for the manager     |
| `username` | `TEXT`        | `UNIQUE NOT NULL`               | Manager's username            |
| `password` | `TEXT`        | `NOT NULL`                      | Manager's hashed password     |
| `auth_token`| `TEXT`        | `UNIQUE`                        | Active authentication token   |

*Note: Passwords should be hashed in a production environment. This example stores them as plain text for simplicity.*

### `customers`

| Column       | Type    | Constraints                     | Description                     |
| :----------- | :------ | :------------------------------ | :------------------------------ |
| `account_id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT`     | Unique account ID for customer  |
| `name`       | `TEXT`  | `NOT NULL`                      | Customer's full name            |
| `email`      | `TEXT`  | `UNIQUE NOT NULL`               | Customer's email address        |
| `password`   | `TEXT`  | `NOT NULL`                      | Customer's hashed password      |
| `balance`    | `REAL`  | `NOT NULL DEFAULT 0.0`          | Current account balance         |
| `auth_token` | `TEXT`  | `UNIQUE`                        | Active authentication token     |

*Note: Passwords should be hashed in a production environment.*

### `transactions`

| Column           | Type      | Constraints                                       | Description                                     |
| :--------------- | :-------- | :------------------------------------------------ | :---------------------------------------------- |
| `transaction_id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT`                       | Unique ID for the transaction                   |
| `account_id`     | `INTEGER` | `NOT NULL, FOREIGN KEY (account_id) REFERENCES customers (account_id)` | ID of the customer account involved         |
| `transaction_type`| `TEXT`   | `NOT NULL`                                        | Type of transaction (e.g., 'deposit', 'withdrawal', 'transfer_in', 'transfer_out') |
| `amount`         | `REAL`    | `NOT NULL`                                        | Amount of the transaction                       |
| `timestamp`      | `DATETIME`| `NOT NULL`                                        | Date and time of the transaction                |
| `description`    | `TEXT`    |                                                   | Optional description for the transaction        |

## Authentication

Authentication is handled using Bearer tokens.
1.  **Login:** Managers or customers log in with their credentials. Upon successful login, the API returns an `access_token`.
2.  **Authenticated Requests:** For endpoints that require authentication, the client must include the `access_token` in the `Authorization` header with the `Bearer` scheme.
    Example: `Authorization: Bearer <your_access_token>`
3.  **Logout:** The logout endpoint invalidates the `auth_token` in the database.

## Project Structure


. ├── venv/ # Virtual environment directory (if created) ├── app.py # Main Flask application file ├── bank.db # SQLite database file (created on run) ├── requirements.txt # Python package dependencies └── README.md # This file
*(Adjust `app.py` if your main file has a different name)*

## Future Improvements

-   **Password Hashing:** Implement strong password hashing (e.g., using Werkzeug's security helpers or libraries like bcrypt/argon2) instead of storing plain text passwords.
-   **JWT for Tokens:** Use JSON Web Tokens (JWTs) for more robust and stateless authentication tokens.
-   **Input Validation:** Enhance input validation for all API endpoints using a library like Marshmallow or Pydantic for more structured validation.
-   **Error Handling:** Implement more comprehensive and standardized error handling.
-   **Testing:** Add unit and integration tests to ensure code quality and reliability.
-   **Database Migrations:** Use a tool like Alembic (for SQLAlchemy) or Flask-Migrate if the schema evolves significantly.
-   **Asynchronous Tasks:** For potentially long-running operations (e.g., generating large reports), consider using a task queue like Celery.
-   **Containerization:** Dockerize the application for easier deployment and scalability.
-   **CI/CD:** Implement a CI/CD pipeline for automated testing and deployment.
-   **More Complex Banking Features:** Add features like loan applications, scheduled payments, different account types, etc.

## License

This project is licensed under the Apache License 2.0. See the `LICENSE` file for details (if you create one, or refer to the URL: `http://www.apache.org/licenses/LICENSE-2.0.html`).

