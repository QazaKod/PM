from sqlalchemy import Column, String, Integer, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Program(Base):
    __tablename__ = "programs"

    id = Column(String, primary_key=True, index=True)
    code = Column(String)
    faculty = Column(String)
    name = Column(String)
    degree = Column(String)
    duration_years = Column(Integer)
    approx_cost_per_year_kzt = Column(Integer)
    format = Column(String)
    language = Column(JSON)  # Will store list of strings
    unt_subjects = Column(JSON)  # Will store list of strings
    description = Column(String)
    aliases = Column(JSON)  # US3 requirement program aliases
    codes = Column(JSON)    # US3 requirement program codes

    # Relationships
    requirements = relationship("Requirement", back_populates="program")


class FAQ(Base):
    __tablename__ = "faqs"

    id = Column(String, primary_key=True, index=True)
    question = Column(String)
    answer = Column(String)
    keywords = Column(JSON)  # Will store list of strings


class Requirement(Base):
    """
    Flattened representation of requirements.json for US3.
    """
    __tablename__ = "requirements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    program_id = Column(String, ForeignKey("programs.id"), index=True)
    
    # Classification
    category = Column(String)  # domestic / international
    level = Column(String)     # undergraduate / graduate
    topic = Column(String)     # exams / prerequisites / language
    
    # Metadata
    status = Column(String)
    source = Column(String)
    checked_on = Column(String)
    verified_on = Column(String)
    review_due = Column(String)
    admission_period = Column(String)
    valid_until = Column(String)
    verification_note = Column(String)
    
    # Localized texts
    text_en = Column(String)
    text_ru = Column(String)
    text_kk = Column(String)

    # Relationships
    program = relationship("Program", back_populates="requirements")
