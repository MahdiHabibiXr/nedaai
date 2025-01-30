import sqlite3

import msgs

DB_NAME = "sessions/nedaai.db"


def create_users_table():
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect(DB_NAME)

    # Create a cursor object
    cursor = conn.cursor()

    # Create the 'users' table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Auto-incremented primary key
        chat_id INTEGER,                -- Telegram's unique user ID
        username TEXT,                         -- Optional Telegram username
        credits INTEGER DEFAULT 0,            -- Remaining free credits
        audio TEXT,                            -- Path or URL of the latest audio file
        gender TEXT,
        refs INTEGER DEFAULT 0,               -- Number of invitations
        model_name TEXT,
        duration INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- User creation timestamp
    );
    """
    )

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

    print("Users table created successfully.")


def create_generations_table():
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect(DB_NAME)

    # Create a cursor object
    cursor = conn.cursor()

    # Create the 'generations' table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Auto-incremented primary key
        chat_id INTEGER,                       -- Telegram's unique user ID
        audio TEXT,                            -- Input text for generation
        model_name TEXT,                            -- Model used for generation
        duration INTEGER,                      -- Duration of the generated audio
        replicate_id INTEGER,                 -- ID of the original generation
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Generation creation timestamp
    );
    """
    )

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

    print("Generations table created successfully.")


def add_generation(chat_id, audio, model, duartion, replicate_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO generations (chat_id, audio, model_name, duration, replicate_id) 
        VALUES (?, ?, ?, ?, ?)
    """,
        (chat_id, audio, model, duartion, replicate_id),
    )
    conn.commit()
    conn.close()


# Function to check if a user exists
def user_exists(chat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


# Function to create a new user
def create_user(chat_id, username=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (chat_id, username, credits) 
        VALUES (?, ?, ?)
    """,
        (chat_id, username, msgs.initial_gift),
    )
    conn.commit()
    conn.close()


def update_user_column(chat_id, column, value, increment=False):
    """
    Update a specific column for a user in the 'users' table.

    Args:
        chat_id (int): The chat_id of the user to update.
        column (str): The column to update.
        value: The value to set or increment the column by.
        increment (bool): If True, increments the column value; otherwise, sets it.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if increment:
        # Increment the column value
        query = f"UPDATE users SET {column} = {column} + ? WHERE chat_id = ?"
    else:
        # Set the column value
        query = f"UPDATE users SET {column} = ? WHERE chat_id = ?"

    cursor.execute(query, (value, chat_id))
    conn.commit()
    conn.close()


def get_users_columns(chat_id, columns):
    """
    Retrieve values from specific column(s) in the 'users' table for a given chat_id.

    Args:
        chat_id (int): The chat ID of the user.
        columns (list or str): Column name(s) to retrieve. Can be a single column or a list of columns.

    Returns:
        dict or None: A dictionary of column-value pairs if the user exists, otherwise None.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Ensure columns is a list to handle both single and multiple columns
    if isinstance(columns, str):
        columns = [columns]

    # Convert columns list to a comma-separated string for the SQL query
    columns_str = ", ".join(columns)

    try:
        query = f"SELECT {columns_str} FROM users WHERE chat_id = ?"
        cursor.execute(query, (chat_id,))
        result = cursor.fetchone()

        if result:
            return dict(
                zip(columns, result)
            )  # Map columns to their corresponding values
        else:
            return None  # User not found
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        conn.close()


def add_gender_column_to_users():
    """
    Add a 'gender' column to the 'users' table if it doesn't already exist.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Check if the 'gender' column already exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if "gender" not in columns:
        # Add the 'gender' column
        cursor.execute("ALTER TABLE users ADD COLUMN gender TEXT")
        conn.commit()
        print("Gender column added to users table.")
    else:
        print("Gender column already exists in users table.")

    conn.close()


def generate_users_report():
    """
    Generate a report about the users in the 'users' table.

    Returns:
        str: A formatted string report about the users.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        if total_users == 0:
            return "No users found in the database."

        cursor.execute("SELECT COUNT(*) FROM users WHERE credits = 120")
        credits_120 = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE credits <= 120 AND credits > 100"
        )
        credits_120_100 = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE credits <= 100 AND credits > 50"
        )
        credits_100_50 = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE credits <= 50 AND credits > 25"
        )
        credits_50_25 = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE credits <= 25 AND credits >= 0"
        )
        credits_25_0 = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE audio IS NOT NULL")
        audio_not_none = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE refs > 0")
        refs_greater_than_0 = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE gender = 'male'")
        male_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE gender = 'female'")
        female_users = cursor.fetchone()[0]

        report_lines = [
            "📊 **Users Report:**\n",
            f"👥 **Total:** {total_users}\n",
            f"💳 **Credits = 120:** {credits_120} ({credits_120 / total_users * 100:.2f}%)",
            f"💳 **Credits 120-100:** {credits_120_100} ({credits_120_100 / total_users * 100:.2f}%)",
            f"💳 **Credits 100-50:** {credits_100_50} ({credits_100_50 / total_users * 100:.2f}%)",
            f"💳 **Credits 50-25:** {credits_50_25} ({credits_50_25 / total_users * 100:.2f}%)",
            f"💳 **Credits 25-0:** {credits_25_0} ({credits_25_0 / total_users * 100:.2f}%)\n",
            f"🎧 **Audio not none:** {audio_not_none} ({audio_not_none / total_users * 100:.2f}%)\n",
            f"🔗 **Refs > 0:** {refs_greater_than_0} ({refs_greater_than_0 / total_users * 100:.2f}%)\n",
            f"♂️ **Male:** {male_users} ({male_users / total_users * 100:.2f}%)",
            f"♀️ **Female:** {female_users} ({female_users / total_users * 100:.2f}%)",
        ]

        return "\n".join(report_lines)
    except sqlite3.Error as e:
        return f"Database error: {e}"
    finally:
        conn.close()


def generate_generations_report():
    """
    Generate a report about the generations in the 'generations' table.

    Returns:
        str: A formatted string report about the generations.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM generations")
        total_generations = cursor.fetchone()[0]

        if total_generations == 0:
            return "No generations found."

        cursor.execute("SELECT SUM(duration) FROM generations")
        total_duration = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM generations")
        unique_users = cursor.fetchone()[0]

        average_duration_per_user = total_duration / unique_users if unique_users else 0

        cursor.execute(
            "SELECT model_name, COUNT(*), SUM(duration) FROM generations GROUP BY model_name ORDER BY COUNT(*) DESC"
        )
        model_stats = cursor.fetchall()

        report_lines = [
            "📊 **Generations Report:**\n",
            f"🔢 **Total:** {total_generations}",
            f"⏳ **Duration:** {total_duration} sec",
            f"👥 **Users:** {unique_users}",
            f"📈 **Avg/User:** {average_duration_per_user:.2f} sec",
            f"🛠️ **Models:** {len(model_stats)}\n",
        ]

        for rank, (model_name, count, duration) in enumerate(model_stats, start=1):
            percentage = (count / total_generations) * 100
            report_lines.append(
                f"{rank}. **{model_name}:** {percentage:.2f}%, {count} generations, {duration} sec"
            )

        return "\n".join(report_lines)
    except sqlite3.Error as e:
        return f"Database error: {e}"
    finally:
        conn.close()
