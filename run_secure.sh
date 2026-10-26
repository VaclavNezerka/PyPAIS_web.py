#!/bin/bash
# Runs AIBAL like run_prod.sh (gunicorn), but asks for the database password instead of reading it from .env.
# (It used to run "python app.py" - Flask's development server with debug mode and a hard-coded secret key.)

echo "Starting AIBAL securely..."
echo ""

# Prompt for password securely; values in the environment take precedence over .env
read -s -p "DB Password: " db_pass
echo ""

source venv_aibal/bin/activate
# The password is only available to this single command execution
DB_PASSWORD="$db_pass" gunicorn app:app   --bind 0.0.0.0:5011   --workers 4

# Clear the password variable immediately
unset db_pass

echo ""
echo "Application finished. Password cleared from memory."
