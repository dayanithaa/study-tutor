import statistics
from datetime import datetime
from collections import defaultdict


def analyze_user_performance(user_data):
    """Analyze user performance"""
    topics = user_data.get('topics', {})
    
    analysis = {
        'overall_scores': {'intuition': [], 'memory': [], 'application': []},
        'topic_performance': {},
        'temporal_data': [],
        'weak_areas': []
    }
    
    for topic_key, topic_data in topics.items():
        topic_name = topic_data.get('name', topic_key)
        topic_scores = {'intuition': [], 'memory': [], 'application': []}
        
        for subtopic_key, subtopic_data in topic_data.get('subtopics', {}).items():
            for assessment in subtopic_data.get('assessments', []):
                for dim, score in assessment['scores'].items():
                    analysis['overall_scores'][dim].append(score)
                    topic_scores[dim].append(score)
                
                avg_score = sum(assessment['scores'].values()) / 3
                questions = assessment.get('questions', [])
                # Calculate question count - default to 10 if not available (typical assessment size)
                question_count = len(questions) if questions and isinstance(questions, list) else 10
                
                # Normalize date format (handle ISO format from database)
                date_str = assessment['date']
                if 'T' in date_str:

                    date_str = date_str.split('T')[0]
                elif ' ' in date_str and len(date_str) > 10:

                    date_str = date_str.split(' ')[0]
                
                analysis['temporal_data'].append({
                    'date': date_str,
                    'topic': topic_name,
                    'score': avg_score,
                    'question_count': question_count,
                    'assessment_id': assessment.get('assessment_id', ''),
                    'subtopic': subtopic_key
                })
        
        avg_scores = {
            dim: sum(scores) / len(scores) if scores else 0
            for dim, scores in topic_scores.items()
        }
        overall_avg = sum(avg_scores.values()) / 3
        
        analysis['topic_performance'][topic_key] = {
            'name': topic_name,
            'avg_scores': avg_scores,
            'overall_avg': overall_avg
        }
        
        if overall_avg < 60:
            weak_dim = min(avg_scores, key=avg_scores.get)
            analysis['weak_areas'].append({
                'topic': topic_name,
                'score': overall_avg,
                'dimension': weak_dim
            })
    
    analysis['temporal_data'].sort(key=lambda x: x['date'])
    return analysis


def calculate_analytics(analysis):
    """Calculate analytics for frontend with comprehensive chart data"""
    from chart_data import (
        generate_topic_accuracy_trend, generate_topic_improvement_data,
        generate_daily_question_counts, generate_improvement_trend_data
    )
    
    overall_avg = {
        dim: round(sum(scores) / len(scores)) if scores else 0
        for dim, scores in analysis['overall_scores'].items()
    }
    
    topic_summary = []
    for topic_data in analysis['topic_performance'].values():
        topic_info = {
            'name': topic_data['name'],
            'avgScore': round(topic_data['overall_avg'], 1),
            'intuition': round(topic_data['avg_scores']['intuition'], 1),
            'memory': round(topic_data['avg_scores']['memory'], 1),
            'application': round(topic_data['avg_scores']['application'], 1)
        }
        
        # Add comprehensive chart data for each topic
        topic_info['chartData'] = {
            'accuracyTrend': generate_topic_accuracy_trend(topic_data['name'], analysis['temporal_data']),
            'improvementProgress': generate_topic_improvement_data(topic_data['name'], analysis['temporal_data']),
            'subtopicImprovements': {}
        }
        
        topic_summary.append(topic_info)
    
    topic_summary.sort(key=lambda x: x['avgScore'])
    
    improvement_trend = []
    for item in analysis['temporal_data']:
        improvement_trend.append({
            'date': item['date'],
            'score': round(item['score'])
        })
    
    # Generate daily question counts
    daily_questions = generate_daily_question_counts(analysis['temporal_data'])
    
    # Generate overall improvement trend data
    overall_improvement_trend = generate_improvement_trend_data(analysis['temporal_data'], overall_avg)
    
    return {
        'overallAvg': overall_avg,
        'topicSummary': topic_summary,
        'weakAreas': analysis['weak_areas'],
        'improvementTrend': improvement_trend,
        'totalAssessments': len(analysis['temporal_data']),
        'dailyQuestions': daily_questions,
        'overallImprovementTrend': overall_improvement_trend
    }

