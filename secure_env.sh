#!/bin/bash
# Secure environment setup for PyPAIS application
# This script sets environment variables without exposing sensitive data

# Set non-sensitive environment variables
export SECRET_KEY_LENGTH=32
export HASH_METHOD="pbkdf2:sha256"
export SALT_LENGTH=16
export DB_USERNAME="pypais_small"

# Function to securely prompt for password
set_db_password() {
    echo "Please enter the database password:"
    read -s -p "Password: " DB_PASSWORD
    export DB_PASSWORD
    echo  # Add a newline after password input
}

# Call the function to set password
set_db_password

# Clear command history to prevent password exposure
history -c 2>/dev/null || true

echo ""
echo "✓ Environment variables configured successfully"
echo "✓ SECRET_KEY_LENGTH: $SECRET_KEY_LENGTH"
echo "✓ HASH_METHOD: $HASH_METHOD"
echo "✓ SALT_LENGTH: $SALT_LENGTH"  
echo "✓ DB_USERNAME: $DB_USERNAME"
echo "✓ DB_PASSWORD: [SECURED]"
echo ""
echo "Your PyPAIS application is now ready to run!"
echo "Use: python app.py"
