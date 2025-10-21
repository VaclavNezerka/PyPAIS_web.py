# !/bin/bash
# Script to manage translations for PyPAIS
pybabel extract -F babel.cfg -o messages.pot -k lazy_gettext -k _  -k lazy_pgettext:1c,2 .

# For each language you want to support, run the following command once
# replace 'cs' with the appropriate language code
if [ ! -d "translations/cs/LC_MESSAGES" ]; then
    pybabel init -i messages.pot -d translations -l cs
fi

# update the treanslations with new strings
pybabel update -i messages.pot -d translations

# wait until the user writes the translations in the .po files
read -p  "Are the new strings ready for translation? (yes/no): " ready

# check user input
if [ "$ready" != "yes" ]; then
    # notify the user to complete translations
    echo ""
    echo "Please complete the translations in the .po files before compiling."
    echo "Then run the following command to compile the translations:"
    echo "pybabel compile -d translations"
    exit 1
elif [ "$ready" == "yes" ]; then
    # proceed to compile translations
    echo "Proceeding to compile translations..."
    pybabel compile -d translations
fi
