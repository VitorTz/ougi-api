from psycopg.errors import UniqueViolation
from passlib.context import CryptContext
from psycopg.rows import dict_row
from dotenv import load_dotenv
from typing import Optional
import getpass
import psycopg
import os


load_dotenv()


def get_password_hash(password: str) -> Optional[str]:
    pwd_context = CryptContext(
        schemes=["argon2"],
        deprecated="auto"
    )
    if not password: return None
    return pwd_context.hash(password)


QUERY = """
    INSERT INTO users (
        username,
        email,
        password_hash,
        role
    )
    VALUES
        (%s, %s, %s, 'admin')
    RETURNING
        id, 
        username, 
        email, 
        role
"""


def main():
    print("=== Admin Account Initialization ===")
    
    # 1. Collect data from the terminal
    username = input("Enter admin username: ").strip()
    email = input("Enter admin email: ").strip()
    password = getpass.getpass("Enter admin password: ")
    
    if not username or not email or not password:
        print("Error: Username, email, and password cannot be empty.")
        return

    # 2. Hash the raw password before touching the database
    hashed_password: str = get_password_hash(password)
    
    db_url = os.getenv("DATABASE_URL_DIRECT")
    if not db_url:
        print("Error: DATABASE_URL_DIRECT environment variable is missing.")
        return

    # 3. Connect to the database
    try:
        conn = psycopg.connect(
            db_url,
            row_factory=dict_row
        )
    except Exception as e:
        print(f"Failed to connect to the database: {e}")
        return

    # 4. Execute the insertion query safely
    try:
        with conn.cursor() as cur:
            cur.execute(
                QUERY,
                (username, email, hashed_password)
            )
            
            new_admin = cur.fetchone()        
            conn.commit()
            
            print("\nSuccess! Admin account has been created.")
            print(f"User ID : {new_admin['id']}")
            print(f"Username: {new_admin['username']}")
            print(f"Email   : {new_admin['email']}")
            print(f"Role    : {new_admin['role']}")
    except UniqueViolation:
        conn.rollback()
        print("\nError: An account with this username or email already exists.")
    except Exception as e:
        conn.rollback()
        print(f"\nAn unexpected database error occurred: {e}")        
    finally:
        conn.close()


if __name__ == "__main__":
    main()