
import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func

# Instead of writing SQL like:
# CREATE TABLE users (...)
# You write Python classes, and SQLAlchemy converts them to SQL.

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///learning_analytics.db')
# A Python library that lets you work with databases using Python classes instead of raw SQL

# Create engine and session
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """User model"""
    __tablename__ = 'users'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100))
    joined_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assessments = relationship("Assessment", back_populates="user")
    feedback_history = relationship("FeedbackHistory", back_populates="user")
    analytics_cache = relationship("AnalyticsCache", back_populates="user")


class Assessment(Base):
    """Assessment model"""
    __tablename__ = 'assessments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey('users.id'), nullable=False)
    assessment_id = Column(String(100), nullable=False)  # Original assessment ID from mock data
    topic = Column(String(100), nullable=False)
    subtopic = Column(String(100), nullable=False)
    intuition_score = Column(Integer, nullable=False)
    memory_score = Column(Integer, nullable=False)
    application_score = Column(Integer, nullable=False)
    assessment_date = Column(DateTime, nullable=False)
    questions_data = Column(JSON)  # Store questions and answers as JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="assessments")


class FeedbackHistory(Base):
    """Feedback history model"""
    __tablename__ = 'feedback_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey('users.id'), nullable=False)
    subtopic = Column(String(100))
    feedback_type = Column(String(50))  # 'ai', 'rule-based'
    summary = Column(Text)
    patterns = Column(JSON)
    recommendations = Column(JSON)
    action_items = Column(JSON)
    learning_style_insights = Column(Text)
    ai_powered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="feedback_history")


class AnalyticsCache(Base):
    """Analytics cache model for performance"""
    __tablename__ = 'analytics_cache'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey('users.id'), nullable=False)
    cache_key = Column(String(100), nullable=False)
    cache_data = Column(JSON, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="analytics_cache")


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """Initialize database tables"""
    print("🗄️  Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")


def migrate_mock_data():
    """Migrate data from mock_data.py to database"""
    from mock_data import users as mock_users
    
    print("📦 Migrating mock data to database...")
    
    db = SessionLocal()
    try:
        # Check if data already exists
        existing_users = db.query(User).count()
        if existing_users > 0:
            print(f"⚠️  Database already contains {existing_users} users. Skipping migration.")
            return
        
        for mock_user in mock_users:
            # Create user
            user = User(
                id=mock_user['id'],
                name=mock_user['name'],
                email=mock_user.get('email', ''),
                joined_date=datetime.fromisoformat(mock_user.get('joinedDate', '2024-01-01'))
            )
            db.add(user)
            
            # Create assessments
            for topic_key, topic_data in mock_user.get('topics', {}).items():
                topic_name = topic_data.get('name', topic_key)
                
                for subtopic_key, subtopic_data in topic_data.get('subtopics', {}).items():
                    for assessment_data in subtopic_data.get('assessments', []):
                        assessment = Assessment(
                            user_id=mock_user['id'],
                            assessment_id=assessment_data['assessment_id'],
                            topic=topic_name,
                            subtopic=subtopic_key,
                            intuition_score=assessment_data['scores']['intuition'],
                            memory_score=assessment_data['scores']['memory'],
                            application_score=assessment_data['scores']['application'],
                            assessment_date=datetime.fromisoformat(assessment_data['date']),
                            questions_data=assessment_data.get('questions', [])
                        )
                        db.add(assessment)
        
        db.commit()
        
        # Count migrated data
        user_count = db.query(User).count()
        assessment_count = db.query(Assessment).count()
        
        print(f"✅ Migration complete:")
        print(f"   - {user_count} users migrated")
        print(f"   - {assessment_count} assessments migrated")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def get_user_by_id(user_id: str):
    """Get user from database by ID"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # Convert to mock_data format for compatibility
        user_data = {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'joinedDate': user.joined_date.isoformat() if user.joined_date else None,
            'topics': {}
        }
        
        # Get assessments and organize by topic/subtopic
        assessments = db.query(Assessment).filter(Assessment.user_id == user_id).all()
        
        for assessment in assessments:
            topic_key = assessment.topic.lower().replace(' ', '_')
            
            if topic_key not in user_data['topics']:
                user_data['topics'][topic_key] = {
                    'name': assessment.topic,
                    'prerequisites': [],
                    'subtopics': {}
                }
            
            if assessment.subtopic not in user_data['topics'][topic_key]['subtopics']:
                user_data['topics'][topic_key]['subtopics'][assessment.subtopic] = {
                    'assessments': []
                }
            
            assessment_dict = {
                'assessment_id': assessment.assessment_id,
                'date': assessment.assessment_date.isoformat(),
                'scores': {
                    'intuition': assessment.intuition_score,
                    'memory': assessment.memory_score,
                    'application': assessment.application_score
                },
                'questions': assessment.questions_data or []
            }
            
            user_data['topics'][topic_key]['subtopics'][assessment.subtopic]['assessments'].append(assessment_dict)
        
        return user_data
        
    finally:
        db.close()


def store_feedback(user_id: str, feedback: dict, subtopic: str = None):
    """
    Store AI feedback in database with enhanced metadata
    
    Args:
        user_id: User identifier
        feedback: Feedback dictionary containing analysis results
        subtopic: Optional subtopic for targeted feedback
    """
    db = SessionLocal()
    try:
        # Add metadata to feedback
        enhanced_feedback = feedback.copy()
        enhanced_feedback['stored_at'] = datetime.utcnow().isoformat()
        enhanced_feedback['context_version'] = '1.0'
        
        feedback_record = FeedbackHistory(
            user_id=user_id,
            subtopic=subtopic or feedback.get('subtopic'),
            feedback_type='ai' if feedback.get('ai_powered', False) else 'rule-based',
            summary=feedback.get('summary', ''),
            patterns=feedback.get('patterns', []),
            recommendations=feedback.get('recommendations', []),
            action_items=feedback.get('actionItems', []),
            learning_style_insights=feedback.get('learning_style_insights', ''),
            ai_powered=feedback.get('ai_powered', False)
        )
        
        db.add(feedback_record)
        db.commit()
        
        print(f"✅ Feedback stored for user {user_id}" + (f" (subtopic: {subtopic})" if subtopic else ""))
        return feedback_record.id
        
    except Exception as e:
        print(f"❌ Failed to store feedback: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def get_feedback_history(user_id: str, limit: int = 10, subtopic: str = None):
    """
    Get feedback history for user with optional subtopic filtering
    
    Args:
        user_id: User identifier
        limit: Maximum number of records to return
        subtopic: Optional subtopic filter
    """
    db = SessionLocal()
    try:
        query = (
            db.query(FeedbackHistory)
            .filter(FeedbackHistory.user_id == user_id)
        )
        
        # Add subtopic filter if provided
        if subtopic:
            query = query.filter(FeedbackHistory.subtopic == subtopic)
        
        feedback_records = (
            query.order_by(FeedbackHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        
        history = []
        for record in feedback_records:
            history.append({
                'id': record.id,
                'subtopic': record.subtopic,
                'feedback_type': record.feedback_type,
                'summary': record.summary,
                'patterns': record.patterns,
                'recommendations': record.recommendations,
                'actionItems': record.action_items,
                'learning_style_insights': record.learning_style_insights,
                'ai_powered': record.ai_powered,
                'timestamp': record.created_at.isoformat()
            })
        
        return history
        
    finally:
        db.close()


def update_user_progress(user_id: str, assessment_data: dict):
    """
    Add new assessment data for user with real-time cache invalidation
    
    Args:
        user_id: User identifier
        assessment_data: New assessment data to add
    """
    db = SessionLocal()
    try:
        assessment = Assessment(
            user_id=user_id,
            assessment_id=assessment_data['assessment_id'],
            topic=assessment_data['topic'],
            subtopic=assessment_data['subtopic'],
            intuition_score=assessment_data['scores']['intuition'],
            memory_score=assessment_data['scores']['memory'],
            application_score=assessment_data['scores']['application'],
            assessment_date=datetime.fromisoformat(assessment_data['date']),
            questions_data=assessment_data.get('questions', [])
        )
        
        db.add(assessment)
        db.commit()
        
        # Clear cached analytics since new data was added
        clear_user_cache(user_id)
        
        print(f"✅ New assessment added for user {user_id} - cache cleared for real-time updates")
        
        return assessment.id
        
    except Exception as e:
        print(f"❌ Failed to add assessment: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def get_real_time_progress_summary(user_id: str):
    """
    Get real-time progress summary for dashboard updates
    
    Returns:
        Dictionary with latest progress metrics
    """
    db = SessionLocal()
    try:
        # Get latest assessment
        latest_assessment = (
            db.query(Assessment)
            .filter(Assessment.user_id == user_id)
            .order_by(Assessment.assessment_date.desc())
            .first()
        )
        
        if not latest_assessment:
            return None
        
        # Get assessment count for last 7 days
        from datetime import timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        recent_count = (
            db.query(Assessment)
            .filter(Assessment.user_id == user_id)
            .filter(Assessment.assessment_date >= week_ago)
            .count()
        )
        
        # Calculate recent average
        recent_assessments = (
            db.query(Assessment)
            .filter(Assessment.user_id == user_id)
            .filter(Assessment.assessment_date >= week_ago)
            .all()
        )
        
        if recent_assessments:
            total_scores = {'intuition': 0, 'memory': 0, 'application': 0}
            for assessment in recent_assessments:
                total_scores['intuition'] += assessment.intuition_score
                total_scores['memory'] += assessment.memory_score
                total_scores['application'] += assessment.application_score
            
            count = len(recent_assessments)
            recent_avg = {
                'intuition': round(total_scores['intuition'] / count, 1),
                'memory': round(total_scores['memory'] / count, 1),
                'application': round(total_scores['application'] / count, 1)
            }
        else:
            recent_avg = {'intuition': 0, 'memory': 0, 'application': 0}
        
        return {
            'latest_assessment': {
                'date': latest_assessment.assessment_date.isoformat(),
                'topic': latest_assessment.topic,
                'subtopic': latest_assessment.subtopic,
                'scores': {
                    'intuition': latest_assessment.intuition_score,
                    'memory': latest_assessment.memory_score,
                    'application': latest_assessment.application_score
                }
            },
            'recent_activity': {
                'assessments_last_7_days': recent_count,
                'average_scores_last_7_days': recent_avg
            },
            'updated_at': datetime.utcnow().isoformat()
        }
        
    finally:
        db.close()


def cache_analytics(user_id: str, cache_key: str, analytics_data: dict, expiry_hours: int = 1):
    """
    Cache analytics data for performance optimization
    
    Args:
        user_id: User identifier
        cache_key: Unique key for the cached data
        analytics_data: Analytics data to cache
        expiry_hours: Hours until cache expires
    """
    db = SessionLocal()
    try:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)
        
        # Remove existing cache for this key
        db.query(AnalyticsCache).filter(
            AnalyticsCache.user_id == user_id,
            AnalyticsCache.cache_key == cache_key
        ).delete()
        
        # Add new cache entry
        cache_entry = AnalyticsCache(
            user_id=user_id,
            cache_key=cache_key,
            cache_data=analytics_data,
            expires_at=expires_at
        )
        
        db.add(cache_entry)
        db.commit()
        
        print(f"✅ Analytics cached for user {user_id} (key: {cache_key})")
        
    except Exception as e:
        print(f"❌ Failed to cache analytics: {e}")
        db.rollback()
    finally:
        db.close()


def get_cached_analytics(user_id: str, cache_key: str):
    """
    Retrieve cached analytics data if not expired
    
    Args:
        user_id: User identifier
        cache_key: Cache key to retrieve
        
    Returns:
        Cached analytics data or None if not found/expired
    """
    db = SessionLocal()
    try:
        cache_entry = (
            db.query(AnalyticsCache)
            .filter(
                AnalyticsCache.user_id == user_id,
                AnalyticsCache.cache_key == cache_key,
                AnalyticsCache.expires_at > datetime.utcnow()
            )
            .first()
        )
        
        if cache_entry:
            print(f"✅ Cache hit for user {user_id} (key: {cache_key})")
            return cache_entry.cache_data
        
        return None
        
    finally:
        db.close()


def clear_user_cache(user_id: str):
    """Clear all cached analytics for a user (called when new data is added)"""
    db = SessionLocal()
    try:
        deleted_count = (
            db.query(AnalyticsCache)
            .filter(AnalyticsCache.user_id == user_id)
            .delete()
        )
        
        db.commit()
        
        if deleted_count > 0:
            print(f"✅ Cleared {deleted_count} cache entries for user {user_id}")
        
    except Exception as e:
        print(f"❌ Failed to clear cache: {e}")
        db.rollback()
    finally:
        db.close()


def get_contextual_data(user_id: str, subtopic: str = None):
    """
    Get contextual data for AI feedback generation
    
    Args:
        user_id: User identifier
        subtopic: Optional subtopic for targeted context
        
    Returns:
        Dictionary containing user context, recent assessments, and feedback patterns
    """
    db = SessionLocal()
    try:
        # Get user basic info
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # Get recent assessments (last 30 days)
        from datetime import timedelta
        recent_date = datetime.utcnow() - timedelta(days=30)
        
        assessments_query = (
            db.query(Assessment)
            .filter(Assessment.user_id == user_id)
            .filter(Assessment.assessment_date >= recent_date)
        )
        
        if subtopic:
            assessments_query = assessments_query.filter(Assessment.subtopic == subtopic)
        
        recent_assessments = assessments_query.order_by(Assessment.assessment_date.desc()).all()
        
        # Get recent feedback history
        recent_feedback = get_feedback_history(user_id, limit=5, subtopic=subtopic)
        
        # Calculate performance trends
        performance_trend = []
        for assessment in recent_assessments:
            avg_score = (assessment.intuition_score + assessment.memory_score + assessment.application_score) / 3
            performance_trend.append({
                'date': assessment.assessment_date.isoformat(),
                'topic': assessment.topic,
                'subtopic': assessment.subtopic,
                'avg_score': avg_score,
                'scores': {
                    'intuition': assessment.intuition_score,
                    'memory': assessment.memory_score,
                    'application': assessment.application_score
                }
            })
        
        # Identify recurring patterns from feedback
        recurring_patterns = {}
        for feedback in recent_feedback:
            if feedback.get('patterns'):
                for pattern in feedback['patterns']:
                    pattern_type = pattern.get('type', 'Unknown')
                    if pattern_type not in recurring_patterns:
                        recurring_patterns[pattern_type] = 0
                    recurring_patterns[pattern_type] += 1
        
        context_data = {
            'user_info': {
                'id': user.id,
                'name': user.name,
                'joined_date': user.joined_date.isoformat() if user.joined_date else None
            },
            'recent_assessments': performance_trend,
            'recent_feedback_count': len(recent_feedback),
            'recurring_patterns': recurring_patterns,
            'context_generated_at': datetime.utcnow().isoformat(),
            'subtopic_focus': subtopic
        }
        
        return context_data
        
    finally:
        db.close()


if __name__ == '__main__':
    # Initialize database and migrate data
    init_database()
    migrate_mock_data()
    print("🎉 Database setup complete!")