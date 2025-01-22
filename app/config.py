import os

from db import create_users_table

# Create sessions directory if it doesn't exist
if not os.path.exists("sessions"):
    os.makedirs("sessions")

create_users_table()
