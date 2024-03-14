-- This script creates the database schema directly using SQL syntax
-- KEEP IN MIND that this commands affects the live database, so you 
-- usually want to run this script only when creating DB SCHEMA 


CREATE TABLE companies(
    id SERIAL PRIMARY KEY,
    company_name varchar(50),
    company_address varchar(50)
);

CREATE TABLE users(
    id SERIAL PRIMARY KEY,
    first_name varchar(50) NOT NULL,
    last_name varchar(50) NOT NULL,
    username varchar(50) NOT NULL,
    e_mail varchar(200) NOT NULL,
    company INT REFERENCES companies(id),
    pwd TEXT
);

CREATE TABLE experiments(
    id SERIAL PRIMARY KEY,
    time_stamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by_user INT REFERENCES users(id),
    img BYTEA, --BLOB is BYTEA in postgresql
    img_mask_asphalt BYTEA,
    img_mask_aggregate BYTEA,
    expert_guess decimal(5,2),
    fake_deleted BOOLEAN DEFAULT FALSE,
    info TEXT
);

SELECT * FROM experiments;