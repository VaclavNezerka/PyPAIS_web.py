-- This script creates the database schema directly using SQL syntax
-- KEEP IN MIND that this commands affects the live database, so you 
-- usually want to run this script only when creating DB SCHEMA 

CREATE TABLE companies(
    id SERIAL PRIMARY KEY,
    company_name varchar(50) NOT NULL UNIQUE,
    company_address varchar(50)
);

CREATE TABLE users(
    id SERIAL PRIMARY KEY,
    first_name varchar(50) NOT NULL,
    last_name varchar(50) NOT NULL,
    username varchar(50) NOT NULL UNIQUE,
    e_mail varchar(200) NOT NULL UNIQUE,
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

CREATE VIEW public_users AS SELECT id, first_name, last_name, company FROM users;

INSERT INTO 
companies (company_name, company_address) 
VALUES 
('RSD', 'rsd@fmail.com'),
('CTU', 'ctu@fmail.com');

INSERT INTO 
users (first_name, last_name, username, e_mail, company) 
VALUES 
('Adam', 'Malik', 'amal', 'amal@fmail.com', 1),
('Bdam', 'Nalik', 'bmal', 'bmal@fmail.com', 1),
('Cdam', 'Halik', 'cmal', 'cmal@fmail.com', 2),
('Ddam', 'Lalik', 'dmal', 'dmal@fmail.com', 1);

SELECT * FROM users;