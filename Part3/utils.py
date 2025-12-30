

from datetime import datetime
import random


def calculate_mastery_level(avg_score):
    """Calculate mastery level based on average score"""
    if avg_score >= 90:
        return 'expert'
    elif avg_score >= 75:
        return 'advanced'
    elif avg_score >= 60:
        return 'intermediate'
    else:
        return 'beginner'


def estimate_time_spent(topic):
    """Estimate time spent on topic based on performance"""
    base_time = 45  # Base minutes per topic
    performance_multiplier = 1.5 if topic['avgScore'] < 60 else 1.0
    return int(base_time * performance_multiplier)


def get_last_studied_date():
    """Get mock last studied date"""
    from datetime import timedelta
    
    days_ago = random.randint(1, 7)
    date = datetime.now() - timedelta(days=days_ago)
    return date.strftime('%b %d')


def estimate_assessment_count(topic):
    """Estimate number of assessments for topic"""
    # Base count with some variation based on performance
    base_count = 8
    variation = random.randint(-3, 5)
    return max(3, base_count + variation)


def analyze_user_performance_with_cache(user_data, use_cache=True):
    """Wrapper for analyze_user_performance with caching support"""
    from analytics import analyze_user_performance
    from database import get_cached_analytics, cache_analytics
    
    user_id = user_data.get('id')
    cache_key = f"analysis_{user_id}"
    
    # Try to get cached result
    if use_cache:
        cached = get_cached_analytics(user_id, cache_key)
        if cached:
            return cached
    
    # Perform fresh analysis
    analysis = analyze_user_performance(user_data)
    
    # Cache the results
    if use_cache:
        cache_analytics(user_id, cache_key, analysis, expiry_hours=1)
    
    return analysis


def calculate_analytics_with_cache(analysis, user_id, use_cache=True):
    """Wrapper for calculate_analytics with caching support"""
    from analytics import calculate_analytics
    from database import get_cached_analytics, cache_analytics
    
    cache_key = f"analytics_{user_id}"
    
    # Try to get cached result
    if use_cache:
        cached = get_cached_analytics(user_id, cache_key)
        if cached:
            return cached
    
    # Perform fresh calculation
    analytics = calculate_analytics(analysis)
    
    # Cache the results
    if use_cache:
        cache_analytics(user_id, cache_key, analytics, expiry_hours=1)
    
    return analytics