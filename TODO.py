# TODO FIX BUGS
"""
Image blur can not be alleviated 
"""
# TODO List
# Feasible tasks
"""
Add an insert box for the expert's guess and store the value together with the rest of information.
DAVID ON Automatized mask suggestion (background removal) 
DAVID ON Create an frontend protocol for initial mask (background removal) creation 
Create a protocol for manual adjustments of the suggested mask  
Create a protocol for manual picture cropping  
Add an option for the user to switch between original image and the BW 
Add an option for the user to turn on/off the overlay
Add an option for the user to manually finish the mask denoting the asphalt
Employ suitable database for data storage (and add the UI for submission of final setting)
"""
# (Currently) Not-feasible tasks
"""
Create own model for mask suggestion (background removal) [Not enough data available]   
Develop the model for asphalt recognitions [Not enough data available]
Create UI for managing the old requests [No DB employed yet]
"""
# DONE
"""

"""
# Ideas
"""
1] maybe it would be useful to have a feature that automatically fills all convex gabs smaller than a given parameter 
(as a number in pixels or graphically), this might save a lot of time to a user during the manual annotation of stones/asphalt 

2) store original picture (3 chanel based)
3) manual adjustments are unnecessary (or unwanted)
4) progress bar 
"""


# NEXT SESSION
# 1) set new environment variable 
# **conda env config vars set SECRET_KEY_LENGTH=XX
# 2) set new privileges to DB_USERNAME: 
# **GRANT INSERT ON users TO DB_USERNAME;
# **GRANT USAGE, SELECT ON SEQUENCE users_id_seq TO DB_USERNAME;
# CREATE OR REPLACE VIEW public_users AS SELECT id, first_name, last_name, company, username,e_mail FROM users;
# ALTER TABLE companies RENAME COLUMN id TO company_id;
# CREATE VIEW public_companies AS SELECT company_id, company_name FROM companies;
# GRANT SELECT ON public_companies TO DB_USERNAME;