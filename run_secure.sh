#!/bin/bash
# Secure script to run PyPAIS without exposing passwords

echo "Starting PyPAIS securely..."
echo ""

# Set non-sensitive environment variables
export SECRET_KEY_LENGTH=32
export HASH_METHOD="pbkdf2:sha256"
export SALT_LENGTH=16
export DB_USERNAME="pypais_small"

# Prompt for password securely and run the app immediately
echo "Please enter the database password:"
read -s -p "Password: " db_pass
echo ""

# Run the application with the password as an environment variable
# The password is only available to this single command execution
DB_PASSWORD="$db_pass" python app.py

# Clear the password variable immediately
unset db_pass

echo ""
echo "Application finished. Password cleared from memory."
