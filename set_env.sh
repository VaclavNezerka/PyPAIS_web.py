#!/bin/bash
# Set environment variables for PyPAIS application

export SECRET_KEY_LENGTH=32
export HASH_METHOD="pbkdf2:sha256"
export SALT_LENGTH=16
export DB_USERNAME="pypais_small"

# Prompt for database password securely (won't echo to screen)
echo "Please enter the database password:"
read -s DB_PASSWORD
export DB_PASSWORD

# Clear the password from command history and variables after use
unset HISTFILE

echo "Environment variables set for PyPAIS:"
echo "SECRET_KEY_LENGTH=$SECRET_KEY_LENGTH"
echo "HASH_METHOD=$HASH_METHOD"
echo "SALT_LENGTH=$SALT_LENGTH"
echo "DB_USERNAME=$DB_USERNAME"
echo "DB_PASSWORD=****** (hidden for security)"
echo ""
echo "Note: Password is securely stored in environment variable and not displayed."
