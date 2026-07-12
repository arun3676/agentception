from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/agentception.db")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    display_name = Column(String)
    bio = Column(Text)
    registration_source = Column(String, default="email_password")
    login_count = Column(Integer, default=0)
    current_role = Column(String)
    target_role = Column(String)
    location_preference = Column(String)
    skills_json = Column(JSON)
    resume_token = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class AIResource(Base):
    __tablename__ = "ai_resources"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    url = Column(String, nullable=False)
    category = Column(String)
    tags = Column(JSON, default=list)
    difficulty = Column(String)
    cost = Column(String)
    verified = Column(Boolean, default=True)
    upvotes = Column(Integer, default=0)
    added_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    featured = Column(Boolean, default=False)


class ResourceBookmark(Base):
    __tablename__ = "resource_bookmarks"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    resource_id = Column(String, ForeignKey("ai_resources.id"), nullable=False)
    notes = Column(Text)
    completed = Column(Boolean, default=False)
    bookmarked_at = Column(DateTime, server_default=func.now())

    user = relationship("User")
    resource = relationship("AIResource")


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String)
    topic = Column(String)
    expertise_level = Column(String)
    path_data_json = Column(JSON, nullable=False)
    target_role = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_archived = Column(Boolean, default=False)

    user = relationship("User")


class SkillGap(Base):
    __tablename__ = "skill_gaps"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    learning_path_id = Column(String, ForeignKey("learning_paths.id"))
    target_role = Column(String)
    missing_skills = Column(JSON)
    recommended_resources = Column(JSON)
    ai_analysis = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User")
    learning_path = relationship("LearningPath")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    resume_token = Column(String, unique=True, index=True)
    original_pdf_url = Column(String)
    parsed_data_json = Column(JSON)
    tailored_versions_json = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class JobSearch(Base):
    __tablename__ = "job_searches"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    run_id = Column(String, index=True)
    location = Column(String)
    role = Column(String)
    filters_json = Column(JSON)
    results_json = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    learning_path_id = Column(String, ForeignKey("learning_paths.id"))
    job_search_id = Column(String, ForeignKey("job_searches.id"))
    company_name = Column(String)
    job_title = Column(String)
    job_url = Column(String)
    application_status = Column(String)
    tailored_resume_id = Column(String, ForeignKey("resumes.id"))
    outreach_email_id = Column(String)
    applied_at = Column(DateTime)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    learning_path = relationship("LearningPath")
    job_search = relationship("JobSearch")
    resume = relationship("Resume")


class ProgressTracking(Base):
    __tablename__ = "progress_tracking"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    learning_path_id = Column(String, ForeignKey("learning_paths.id"))
    milestone_identifier = Column(String)
    resource_url = Column(String)
    completion_status = Column(String)
    completed_at = Column(DateTime)
    notes = Column(Text)

    user = relationship("User")
    learning_path = relationship("LearningPath")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
