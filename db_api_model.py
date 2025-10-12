"""
Currently using custom based db_api.py
This file is a draft for a switch to SQLModel
"""
import os
# TODO: ***** 
# TODO: CONSIDER a switch to SQLModel 
# TODO: ***** 
import numpy as np
import sqlmodel as sm
from sqlmodel import Field, Relationship

DATABASE_URL = os.getenv('DATABASE_URL', None)
if DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable is not set.")
engine = sm.create_engine(DATABASE_URL)
if not sm.SQLModel.metadata.tables: 
    sm.SQLModel.metadata.create_all(engine)

class User(sm.SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str
    e_mail: str 
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    pwd: str

    def __repr__(self):
        return f"User(id={self.id}, username={self.username}, e_mail={self.e_mail})"
    
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "e_mail": self.e_mail,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "company": self.company
        }
    
    def check_password(self, password: str) -> bool:
        """
        Check if the provided password matches the stored password.
        
        Args:
            password (str): The hashed password to check.

        Returns:
            bool: True if the password matches, False otherwise.
        """
        return self.pwd == password
    
    def set_properties(self, properties: dict) -> None:
        for key, value in properties.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def get_properties(self) -> dict:
        return self.to_dict()   

class Experiment(sm.SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    img_width: int
    img_height: int
    img: bytes
    img_mask_asphalt: bytes | None = None
    img_mask_aggregate: bytes | None = None
    expert_guess: str | None = None
    info: str | None = None
    img_mask_asphalt_manual_correction: bytes | None = None
    img_mask_aggregate_manual_correction: bytes | None = None
    added_by_user: int | None = Field(default=None, foreign_key="user.id")
    active: bool = Field(default=True)
    # internal information
    processed_by_model: str | None = None # e.g., "model_UNET_v1"

    def __repr__(self):
        return f"Experiment(id={self.id}, added_by_user={self.added_by_user}, active={self.active})"
    
    def to_dict(self):
        return self.__dict__
    
    def save_to_db(self, session: sm.Session) -> None:
        session.add(self)
        session.commit()
        session.refresh(self)

    def set_properties(self, properties: dict) -> None:
        for key, value in properties.items():
            if hasattr(self, key):
                setattr(self, key, value)
        session = sm.Session(engine)
        self.save_to_db(session)

    def get_properties(self) -> dict:
        return self.to_dict()
    
    def set_properties(self, properties: dict) -> None:
        for key, value in properties.items():
            if hasattr(self, key):
                if isinstance(value, np.ndarray):
                    value = value.tobytes()
                setattr(self, key, value)

class Company(sm.SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    address: str | None = None
    admins: list["Admin"] = Relationship(back_populates="company")
    users: list[User] = Relationship(back_populates="company")
    company_key: str | None = None  # New field for company key

class Admin(sm.SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    company_id: int = Field(foreign_key="company.id")
    user: User = Relationship(back_populates="admins")
    company: Company = Relationship(back_populates="admins")

def load_experiment_by_id(experiment_id: int) -> Experiment | None:
    with sm.Session(engine) as session:
        response = session.get(Experiment, experiment_id)
    return response

def load_user_by_username(username: str) -> User | None:
    with sm.Session(engine) as session:
        statement = sm.select(User).where(User.username == username)
        response = session.exec(statement).first()
    return response

def load_user_by_email(e_mail: str) -> User | None:
    with sm.Session(engine) as session:
        statement = sm.select(User).where(User.e_mail == e_mail)
        response = session.exec(statement).first()
    return response

def load_user_by_id(user_id: int) -> User | None:
    with sm.Session(engine) as session:
        response = session.get(User, user_id)
    return response

# TODO: ***** 
# TODO: END --- CONSIDER a switch to SQLModel 
# TODO: ***** 