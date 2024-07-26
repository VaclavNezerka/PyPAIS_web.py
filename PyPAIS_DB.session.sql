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
    current_state varchar(10) DEFAULT 'pending' CHECK (current_state IN ('pending', 'processing', 'prepared', 'started' , 'finished')),
    fake_deleted BOOLEAN DEFAULT FALSE,
    finished BOOLEAN DEFAULT FALSE,
    info TEXT
);

ALTER TABLE experiments ADD COLUMN img_width INT DEFAULT NULL;
ALTER TABLE experiments ADD COLUMN img_height INT DEFAULT NULL;
ALTER TABLE experiments ALTER COLUMN current_state varchar(10) DEFAULT 'pending' CHECK (current_state IN ('pending', 'processing', 'prepared', 'started' , 'finished', 'current_experiment'));
ALTER table experiments add column asphalt_ratio decimal(5,2) DEFAULT NULL;
ALTER table experiments add column active BOOLEAN DEFAULT FALSE;
-- integer in range 0/255
ALTER table experiments add column entropy_min_threshold INT DEFAULT NULL;
ALTER table experiments add column entropy_max_threshold INT DEFAULT NULL;
ALTER table experiments add column intensity_min_threshold INT DEFAULT NULL;
ALTER table experiments add column intensity_max_threshold INT DEFAULT NULL;
ALTER table experiments add column blur INT DEFAULT NULL;

ALTER TABLE experiments ADD COLUMN intensity_min_threshold_1 INT DEFAULT NULL;
ALTER TABLE experiments ADD COLUMN intensity_max_threshold_1 INT DEFAULT NULL;
-- rename the intensity_min_threshold to intensity_min_threshold_0
ALTER TABLE experiments RENAME COLUMN intensity_min_threshold TO intensity_min_threshold_0;
ALTER TABLE experiments RENAME COLUMN intensity_max_threshold TO intensity_max_threshold_0;
-- alter table experiments add column finished BOOLEAN DEFAULT FALSE;


INSERT INTO experiments (added_by_user) VALUES (31) RETURNING id;

SELECT id, added_by_user, asphalt_ratio FROM experiments ORDER BY id DESC;
-- SELECT * FROM experiments filter out the last 5 rows;
-- SELECT * FROM experiments LIMIT 5 OFFSET (SELECT COUNT(*) FROM experiments)-5;
-- SELECT id, entropy_min_threshold,entropy_max_threshold,intensity_min_threshold,intensity_max_threshold,blur FROM experiments LIMIT 5 OFFSET (SELECT COUNT(*) FROM experiments)-5;
SELECT id, img_width, img_height, added_by_user, active, entropy_min_threshold,entropy_max_threshold,intensity_min_threshold_0,intensity_max_threshold_0,intensity_min_threshold_1,intensity_max_threshold_1,blur FROM experiments ORDER BY id DESC LIMIT 5;
UPDATE experiments SET added_by_user=26, asphalt_ratio=0.5 WHERE id=91;
-- delete from experiments where id=1;

delete from experiments where id > 30;

INSERT INTO experiments (added_by_user, img, img_mask_asphalt, img_mask_aggregate, expert_guess, info, current_state) 
VALUES 
(15, 'img1', 'mask1', 'mask2', 0.5, 'info1', 'prepared'),
(31, 'img2', 'mask3', 'mask4', 0.6, 'info2', 'finished'),
(31, 'img3', 'mask5', 'mask6', 0.7, 'info3', 'pending'),
(31, 'img4', 'mask7', 'mask8', 0.8, 'info4', 'pending'),
(31, 'img4', 'mask7', 'mask8', 0.8, 'info4', 'processing'),
(15, 'img4', 'mask7', 'mask8', 0.8, 'info4', 'started');

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

GRANT INSERT ON experiments TO pypais_small;

-- grant all privileges on all tables in schema public to pypais_small;
GRANT ALL PRIVILEGES ON experiments TO pypais_small;

GRANT USAGE, SELECT ON SEQUENCE experiments_id_seq TO pypais_small;
GRANT UPDATE ON public_users TO pypais_small;