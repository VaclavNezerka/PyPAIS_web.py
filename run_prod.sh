#!/bin/bash
# Secure script to run PyPAIS without exposing passwords

echo "Starting AIBAL"
echo ""

# Run the application with the password as an environment variable
source venv_aibal/bin/activate
# gunicorn app:app   --bind 127.0.0.1:5011   --workers 4
gunicorn app:app   --bind 0.0.0.0:5011   --workers 4

echo ""
echo "Application finished."
