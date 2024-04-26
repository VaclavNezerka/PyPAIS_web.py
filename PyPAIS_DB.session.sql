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
    current_state varchar(10) DEFAULT 'pending' CHECK (current_state IN ('pending', 'processing', 'prepared', 'started' , 'finished')
    fake_deleted BOOLEAN DEFAULT FALSE,
    finished BOOLEAN DEFAULT FALSE,
    info TEXT
);

ALTER TABLE experiments add COLUMN current_state varchar(10) DEFAULT 'pending' CHECK (current_state IN ('pending', 'processing', 'prepared', 'started' , 'finished'));

SELECT * FROM experiments;

INSERT INTO experiments (added_by_user, img, img_mask_asphalt, img_mask_aggregate, expert_guess, info, current_state) 
VALUES 
(31, 'img1', 'mask1', 'mask2', 0.5, 'info1', 'prepared'),
(31, 'img2', 'mask3', 'mask4', 0.6, 'info2', 'finished'),
(31, 'img3', 'mask5', 'mask6', 0.7, 'info3', 'pending'),
(31, 'img4', 'mask7', 'mask8', 0.8, 'info4', 'pending'),
(31, 'img4', 'mask7', 'mask8', 0.8, 'info4', 'processing'),
(31, 'img4', 'mask7', 'mask8', 0.8, 'info4', 'started');

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

SELECT id, time_stamp, expert_guess FROM experiments where added_by_user=31 AND current_state='finished';


SELECT pwd FROM users;
SELECT * FROM public_users;

DATABASE pypais;

-- 21. 3. UPDATE PRIVILEGES
CREATE OR REPLACE VIEW public_users AS SELECT id, first_name, last_name, company, username, e_mail, pwd FROM users;
ALTER TABLE companies RENAME COLUMN id TO company_id;
CREATE VIEW public_companies AS SELECT company_id, company_name FROM companies;
GRANT SELECT ON public_companies TO pypais_small;
ALTER TABLE experiments add COLUMN finished BOOLEAN DEFAULT FALSE;

SELECT company_id FROM public_companies WHERE company_id=1 LIMIT 1;

SELECT experiment FROM experiments WHERE added_by_user=1 LIMIT 1;

GRANT SELECT ON experiments TO pypais_small;