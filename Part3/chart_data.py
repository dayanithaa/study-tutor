

from datetime import datetime, timedelta
from collections import defaultdict


def generate_daily_question_counts(temporal_data):
    
    if not temporal_data:
        return []
    
    # Group questions by date
    daily_question_counts = defaultdict(int)
    daily_scores = defaultdict(list)
    daily_assessments = defaultdict(list)
    
    # Process temporal data to count actual questions per day
    for item in temporal_data:
        try:
            # Parse date (handle different formats)
            if isinstance(item['date'], str):
                try:
                    date_obj = datetime.strptime(item['date'], '%Y-%m-%d')
                except ValueError:
                    try:
                        date_obj = datetime.strptime(item['date'], '%m/%d/%Y')
                    except ValueError:
                        continue
            else:
                date_obj = item['date']
            
            date_key = date_obj.strftime('%Y-%m-%d')
            
            # Count actual questions from this assessment
            question_count = item.get('question_count', 0)
            daily_question_counts[date_key] += question_count
            daily_scores[date_key].append(item['score'])
            daily_assessments[date_key].append({
                'topic': item.get('topic', ''),
                'subtopic': item.get('subtopic', ''),
                'questions': question_count,
                'score': item['score']
            })
            
        except (KeyError, TypeError, ValueError):
            continue
    
    # Find the actual date range from the data
    if not daily_question_counts:
        return []
    
    # Get all dates with data and sort them
    dates_with_data = sorted(daily_question_counts.keys())
    
    # Create complete date range from first to last assessment date
    start_date = datetime.strptime(dates_with_data[0], '%Y-%m-%d')
    end_date = datetime.strptime(dates_with_data[-1], '%Y-%m-%d')
    
    # Generate data for ALL dates in range (including zero counts for dates with no activity)
    daily_data = []
    current_date = start_date
    
    while current_date <= end_date:
        date_key = current_date.strftime('%Y-%m-%d')
        total_questions = daily_question_counts.get(date_key, 0)
        scores = daily_scores.get(date_key, [])
        avg_accuracy = round(sum(scores) / len(scores)) if scores else 0
        assessments_info = daily_assessments.get(date_key, [])
        
        daily_data.append({
            'date': date_key,
            'dayName': current_date.strftime('%a'),
            'questionCount': total_questions,
            'accuracy': avg_accuracy,
            'assessments': assessments_info
        })
        
        current_date += timedelta(days=1)
    
    return daily_data


def generate_improvement_trend_data(temporal_data, overall_avg):
    """Generates improvement trend data from actual assessment history ONLY using real dates"""
    
    if not temporal_data:
        return []
    
    # Sort temporal data by date
    sorted_data = sorted(temporal_data, key=lambda x: x['date'])
    
    # Group by actual weeks from the data
    weekly_scores = defaultdict(list)
    
    for item in sorted_data:
        try:
            date_obj = datetime.strptime(item['date'], '%Y-%m-%d')
            week_key = f"{date_obj.year}-W{date_obj.isocalendar()[1]:02d}"
            weekly_scores[week_key].append(item['score'])
        except (ValueError, KeyError):
            continue
    
    # Calculate weekly averages from real data only
    trend_data = []
    week_keys = sorted(weekly_scores.keys())
    
    # Use actual weeks with data (up to last 6 weeks)
    for i, week_key in enumerate(week_keys[-6:]):
        avg_score = round(sum(weekly_scores[week_key]) / len(weekly_scores[week_key]))
        year, week_str = week_key.split('-W')
        week_num = int(week_str)
        trend_data.append({
            'week': f'Week {week_num}',
            'score': avg_score
        })
    
    return trend_data


def generate_subtopic_accuracy_trend(user_id, topic_name, subtopic_name):
    """Generates accuracy trend for a specific subtopic showing ALL attempts"""
    from database import SessionLocal, Assessment
    
    db = SessionLocal()
    try:
        # Get all assessments for this specific subtopic, ordered by date
        assessments = db.query(Assessment).filter(
            Assessment.user_id == user_id,
            Assessment.topic == topic_name,
            Assessment.subtopic == subtopic_name
        ).order_by(Assessment.assessment_date.asc()).all()
        
        if not assessments:
            return []
        
        accuracy_data = []
        for i, assessment in enumerate(assessments):
            avg_score = round((assessment.intuition_score + assessment.memory_score + assessment.application_score) / 3)
            accuracy_data.append({
                'attempt': f'Attempt {i + 1}',
                'date': assessment.assessment_date.strftime('%b %d'),
                'score': avg_score
            })
        
        return accuracy_data
        
    finally:
        db.close()


def generate_topic_accuracy_trend(topic_name, temporal_data):
    """Generates accuracy trend data for a specific topic using REAL dates and data only"""
    # Filter data for this topic
    topic_data = [item for item in temporal_data if item.get('topic') == topic_name]
    
    if not topic_data:
        return []
    
    # Sort by date and use actual chronological progression
    sorted_data = sorted(topic_data, key=lambda x: x['date'])
    
    # Generate trend from real data with actual dates - show ALL attempts
    trend_data = []
    attempt_count = {}
    
    for item in sorted_data:
        try:
            date_obj = datetime.strptime(item['date'], '%Y-%m-%d')
            
            # Create a unique key for this assessment
            subtopic_key = item.get('subtopic', 'Unknown')
            if subtopic_key not in attempt_count:
                attempt_count[subtopic_key] = 0
            attempt_count[subtopic_key] += 1
            
            # Use attempt number and date for better labeling
            label = f"{date_obj.strftime('%b %d')} (Attempt {attempt_count[subtopic_key]})"
            
            trend_data.append({
                'week': label,
                'score': round(item['score']),
                'subtopic': subtopic_key,
                'attempt': attempt_count[subtopic_key]
            })
        except (ValueError, KeyError):
            continue
    
    return trend_data


def generate_subtopic_improvement_data(user_id, topic_name, subtopic_name):
    """Generates improvement progress data for a specific subtopic showing actual attempts"""
    from database import SessionLocal, Assessment
    
    db = SessionLocal()
    try:
        # Get all assessments for this specific subtopic, ordered by date
        assessments = db.query(Assessment).filter(
            Assessment.user_id == user_id,
            Assessment.topic == topic_name,
            Assessment.subtopic == subtopic_name
        ).order_by(Assessment.assessment_date.asc()).all()
        
        if not assessments:
            return []
        
        improvement_data = []
        for i, assessment in enumerate(assessments):
            avg_score = round((assessment.intuition_score + assessment.memory_score + assessment.application_score) / 3)
            improvement_data.append({
                'attempt': f'Attempt {i + 1}',
                'score': avg_score,
                'date': assessment.assessment_date.strftime('%b %d'),
                'breakdown': {
                    'intuition': assessment.intuition_score,
                    'memory': assessment.memory_score,
                    'application': assessment.application_score
                }
            })
        
        return improvement_data
        
    finally:
        db.close()


def generate_topic_improvement_data(topic_name, temporal_data):
    """Generates improvement progress data for a specific topic using REAL dates and chronological order"""
    # Filter data for this topic
    topic_data = [item for item in temporal_data if item.get('topic') == topic_name]
    
    if not topic_data:
        return []
    
    # Sort by date to show actual chronological progression
    sorted_data = sorted(topic_data, key=lambda x: x['date'])
    
    improvement_data = []
    for i, item in enumerate(sorted_data):
        try:
            date_obj = datetime.strptime(item['date'], '%Y-%m-%d')
            improvement_data.append({
                'attempt': date_obj.strftime('%b %d'),
                'score': round(item['score'])
            })
        except (ValueError, KeyError):
            continue
    
    return improvement_data


def generate_recent_activity_from_temporal(temporal_data):
    """Generates recent activity timeline from temporal data"""
    if not temporal_data:
        return []
    
    # Sort by date (most recent first)
    sorted_data = sorted(temporal_data, key=lambda x: x['date'], reverse=True)
    
    activities = []
    for item in sorted_data[:7]:
        try:
            date_obj = datetime.strptime(item['date'], '%Y-%m-%d')
            formatted_date = date_obj.strftime('%b %d')
            
            # Generate activity description based on score
            score = round(item['score'])
            topic = item.get('topic', 'Unknown Topic')
            
            if score >= 80:
                action = 'Excelled in'
            elif score >= 60:
                action = 'Completed'
            else:
                action = 'Practiced'
            
            activities.append({
                'date': formatted_date,
                'description': f'{action} {topic} assessment',
                'score': f'{score}%'
            })
        except (ValueError, KeyError):
            continue
    
    return activities