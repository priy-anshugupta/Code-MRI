"""
Database models for persistent storage of branch and analysis data.
"""
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, JSON, 
    ForeignKey, Index, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from typing import Optional

Base = declarative_base()


class Repository(Base):
    """Repository metadata table."""
    __tablename__ = "repositories"
    
    id = Column(String(255), primary_key=True)  # UUID or repo identifier
    url = Column(String(500), nullable=False)
    name = Column(String(255), nullable=True)
    default_branch = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    last_accessed = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # Relationships
    branches = relationship("Branch", back_populates="repository", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_repo_url', 'url'),
        Index('idx_repo_last_accessed', 'last_accessed'),
    )


class Branch(Base):
    """Branch metadata table."""
    __tablename__ = "branches"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(String(255), ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    commit_sha = Column(String(64), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    last_commit_date = Column(DateTime, nullable=True)
    last_analyzed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # Relationships
    repository = relationship("Repository", back_populates="branches")
    analyses = relationship("Analysis", back_populates="branch", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_branch_repo_name', 'repo_id', 'name'),
        Index('idx_branch_commit_sha', 'commit_sha'),
        Index('idx_branch_last_analyzed', 'last_analyzed'),
    )


class Analysis(Base):
    """Analysis results table."""
    __tablename__ = "analyses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(String(255), nullable=False)
    branch_id = Column(Integer, ForeignKey('branches.id', ondelete='CASCADE'), nullable=False)
    commit_sha = Column(String(64), nullable=False)
    analysis_timestamp = Column(DateTime, default=datetime.now, nullable=False)
    
    # Analysis data (stored as JSON for flexibility)
    file_tree = Column(JSON, nullable=False)
    technologies = Column(JSON, nullable=False)  # List of detected technologies
    metrics = Column(JSON, nullable=False)  # Aggregate metrics
    issues = Column(JSON, nullable=False)  # List of issues
    
    # AI-generated content
    ai_summary = Column(Text, nullable=True)
    ai_grading_explanation = Column(Text, nullable=True)
    
    # Detailed scores (stored as JSON)
    detailed_scores = Column(JSON, nullable=True)
    
    # Overall score for quick access
    overall_score = Column(Float, nullable=True)
    overall_grade = Column(String(10), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
    # Relationships
    branch = relationship("Branch", back_populates="analyses")
    
    # Indexes
    __table_args__ = (
        Index('idx_analysis_repo_branch_commit', 'repo_id', 'branch_id', 'commit_sha'),
        Index('idx_analysis_timestamp', 'analysis_timestamp'),
        Index('idx_analysis_commit_sha', 'commit_sha'),
    )


class HistoricalMetric(Base):
    """Historical metrics for trend analysis."""
    __tablename__ = "historical_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(String(255), nullable=False)
    branch_name = Column(String(255), nullable=False)
    commit_sha = Column(String(64), nullable=False)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    
    # Metric values
    overall_score = Column(Float, nullable=True)
    readability_score = Column(Float, nullable=True)
    complexity_score = Column(Float, nullable=True)
    maintainability_score = Column(Float, nullable=True)
    documentation_score = Column(Float, nullable=True)
    security_score = Column(Float, nullable=True)
    performance_score = Column(Float, nullable=True)
    
    # Issue counts
    total_issues = Column(Integer, default=0, nullable=False)
    critical_issues = Column(Integer, default=0, nullable=False)
    high_issues = Column(Integer, default=0, nullable=False)
    medium_issues = Column(Integer, default=0, nullable=False)
    low_issues = Column(Integer, default=0, nullable=False)
    
    # Code metrics
    total_files = Column(Integer, default=0, nullable=False)
    total_lines = Column(Integer, default=0, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_historical_repo_branch', 'repo_id', 'branch_name'),
        Index('idx_historical_timestamp', 'timestamp'),
        Index('idx_historical_commit', 'commit_sha'),
    )


class CacheEntry(Base):
    """Cache metadata for tracking cached analyses."""
    __tablename__ = "cache_entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(255), unique=True, nullable=False)
    repo_id = Column(String(255), nullable=False)
    branch_name = Column(String(255), nullable=False)
    commit_sha = Column(String(64), nullable=False)
    file_path = Column(String(500), nullable=True)  # Path to cached file
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    last_accessed = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    access_count = Column(Integer, default=0, nullable=False)
    size_bytes = Column(Integer, default=0, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_cache_key', 'cache_key'),
        Index('idx_cache_repo_branch_commit', 'repo_id', 'branch_name', 'commit_sha'),
        Index('idx_cache_last_accessed', 'last_accessed'),
    )


# Database session management
class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self, database_url: str = "sqlite:///./code_mri.db"):
        """
        Initialize database manager.
        
        Args:
            database_url: SQLAlchemy database URL
        """
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
            pool_pre_ping=True,
            echo=False
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all database tables."""
        Base.metadata.drop_all(bind=self.engine)
    
    def get_session(self):
        """Get a new database session."""
        return self.SessionLocal()
    
    def close(self):
        """Close the database engine."""
        self.engine.dispose()
