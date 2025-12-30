
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

load_dotenv()

from database import (
    init_database, migrate_mock_data, get_user_by_id, 
    get_feedback_history, SessionLocal, User, Assessment
)
from analytics import analyze_user_performance, calculate_analytics
from ai_feedback import generate_ai_feedback, generate_dashboard_action_items
from utils import analyze_user_performance_with_cache, calculate_analytics_with_cache

app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/api/*": {"origins": "*"}})


@app.after_request
def add_cache_busting(response):
    """Prevent stale data caching"""
    if response.status_code == 200:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
    return response


# Initialize database
try:
    init_database()
    migrate_mock_data()
    print("✅ Database initialized")
except Exception as e:
    print(f"⚠️ Database init warning: {e}")


@app.route('/')
def serve_frontend():
    """Serve main HTML"""
    return send_from_directory('.', 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    if path.startswith('api/') or path.endswith('.py') or path.endswith('.db'):
        return "Not found", 404
    try:
        return send_from_directory('.', path)
    except:
        return "Not found", 404


@app.route('/api/analyze', methods=['POST'])
def analyze_user():
    try:
        request_data = request.json
        
        if not request_data or 'id' not in request_data:
            return jsonify({'success': False, 'error': 'Missing user ID'}), 400
        
        user_id = request_data['id']
        subtopic = request_data.get('subtopic')
        topic = request_data.get('topic')
        
        print(f"\n{'='*60}")
        print(f"📊 Analyze request: {user_id}")
        if topic:
            print(f"📚 Topic: {topic}")
        if subtopic:
            print(f"📖 Subtopic: {subtopic}")
        

        user_data = get_user_by_id(user_id)
        if not user_data:
            return jsonify({'success': False, 'error': f'User {user_id} not found'}), 404
        
        # Get analytics
        analysis = analyze_user_performance_with_cache(user_data, use_cache=True)
        analytics = calculate_analytics_with_cache(analysis, user_id, use_cache=True)
        
        # Generate AI feedback
        print(f"🤖 Generating AI feedback...")
        ai_feedback = generate_ai_feedback(user_data, analytics, subtopic, topic)
        
        print(f"{'='*60}\n")
        
        return jsonify({
            'success': True,
            'analytics': analytics,
            'aiFeedback': ai_feedback,
            'ai_available': not ai_feedback.get('ai_error', False)
        })
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users from database"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return jsonify({
            'success': True,
            'users': [{'id': u.id, 'name': u.name, 'email': u.email or ''} for u in users]
        })
    finally:
        db.close()


@app.route('/api/users/find', methods=['POST'])
def find_user():
    """Find user by ID or name"""
    try:
        request_data = request.json
        if not request_data or 'query' not in request_data:
            return jsonify({'success': False, 'error': 'Missing query parameter'}), 400
        
        query = request_data['query'].strip()
        if not query:
            return jsonify({'success': False, 'error': 'Query cannot be empty'}), 400
        
        db = SessionLocal()
        try:
            # Try to find by ID first (exact match)
            user = db.query(User).filter(User.id == query).first()
            
            # If not found, try to find by name (case-insensitive)
            if not user:
                from sqlalchemy import func
                user = db.query(User).filter(
                    func.lower(User.name) == query.lower()
                ).first()
            
            if user:
                return jsonify({
                    'success': True,
                    'user': {
                        'id': user.id,
                        'name': user.name,
                        'email': user.email or ''
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'User "{query}" not found. Please check the user ID or name.'
                }), 404
                
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error finding user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user-profile/<user_id>', methods=['GET'])
def get_user_profile(user_id):
    """
    Get user profile with REAL data
    - Real recent activity from assessments
    - AI-generated dashboard action items
    - Real statistics from database
    """
    try:
        db = SessionLocal()
        try:
            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            # Get user data and analytics
            user_data = get_user_by_id(user_id)
            if not user_data:
                return jsonify({'success': False, 'error': 'User data not found'}), 404
            
            analysis = analyze_user_performance(user_data)
            analytics = calculate_analytics(analysis)
            
            # Get recent assessments - no date filter to show all activity
            recent_assessments = db.query(Assessment).filter(
                Assessment.user_id == user_id
            ).order_by(Assessment.assessment_date.desc()).limit(10).all()
            
            # Learning streak from REAL assessment dates
            learning_streak = 0
            if recent_assessments:
                assessment_dates = set(a.assessment_date.date() for a in recent_assessments)
                current_date = datetime.now().date()
                while current_date in assessment_dates:
                    learning_streak += 1
                    current_date -= timedelta(days=1)
            
            # Stats from REAL performance
            concepts_mastered = len([t for t in analytics['topicSummary'] if t['avgScore'] >= 75])
            total_concepts = len(analytics['topicSummary'])
            gaps_detected = len([t for t in analytics['topicSummary'] if t['avgScore'] < 60])
            
            # Generate REAL recent activity from actual assessments (latest 3 only)
            recent_activity = []
            for assessment in recent_assessments[:3]:
                avg_score = round((assessment.intuition_score + assessment.memory_score + assessment.application_score) / 3)
                action = 'Excelled in' if avg_score >= 80 else 'Completed' if avg_score >= 60 else 'Practiced'
                
                recent_activity.append({
                    'date': assessment.assessment_date.strftime('%b %d, %Y'),
                    'description': f'{action} {assessment.topic} - {assessment.subtopic}',
                    'score': f'{avg_score}%'
                })
            
            # Generate AI dashboard action items
            print(f"🤖 Generating dashboard action items...")
            action_items = generate_dashboard_action_items(user_id, user_data['name'], analytics)
            
            profile_data = {
                'user_info': {
                    'id': user.id,
                    'name': user.name,
                    'email': user.email or '',
                    'joined_date': user.joined_date.strftime('%B %Y') if user.joined_date else 'Unknown'
                },
                'dashboard_stats': {
                    'concepts_mastered': concepts_mastered,
                    'total_concepts': total_concepts,
                    'learning_streak': learning_streak,
                    'overall_progress': round((analytics['overallAvg']['intuition'] + analytics['overallAvg']['memory'] + analytics['overallAvg']['application']) / 3),
                    'gaps_detected': gaps_detected
                },
                'recent_activity': recent_activity,
                'action_items': action_items,
                'analytics': analytics,
                'ai_available': not any(item.get('ai_error', False) for item in action_items)
            }
            
            return jsonify({'success': True, 'profile': profile_data})
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error getting user profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user-subtopics/<user_id>', methods=['GET'])
def get_user_subtopics(user_id):
    """Get subtopics with scores calculated from REAL assessment data"""
    from sqlalchemy.sql import func
    
    try:
        db = SessionLocal()
        try:
            results = db.query(
                Assessment.topic,
                Assessment.subtopic,
                func.avg(Assessment.intuition_score).label('intuition'),
                func.avg(Assessment.memory_score).label('memory'),
                func.avg(Assessment.application_score).label('application')
            ).filter(
                Assessment.user_id == user_id
            ).group_by(
                Assessment.topic, Assessment.subtopic
            ).all()
            
            topic_subtopics = {}
            for topic, subtopic, intuition, memory, application in results:
                if topic not in topic_subtopics:
                    topic_subtopics[topic] = []
                
                avg_score = round((intuition + memory + application) / 3) if intuition else 0
                
                topic_subtopics[topic].append({
                    'name': subtopic,
                    'score': avg_score,
                    'intuition': round(intuition) if intuition else 0,
                    'memory': round(memory) if memory else 0,
                    'application': round(application) if application else 0
                })
            
            topics_data = [{'name': topic, 'subtopics': subtopics} for topic, subtopics in topic_subtopics.items()]
            
            return jsonify({'success': True, 'topics': topics_data, 'user_id': user_id})
            
        finally:
            db.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/subtopic-improvement/<user_id>/<topic>/<subtopic>', methods=['GET'])
def get_subtopic_improvement_data(user_id, topic, subtopic):
    """Get improvement data showing all attempts for specific subtopic"""
    from chart_data import generate_subtopic_improvement_data
    
    try:
        improvement_data = generate_subtopic_improvement_data(user_id, topic, subtopic)
        return jsonify({
            'success': True,
            'improvement_data': improvement_data,
            'total_attempts': len(improvement_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/subtopic-accuracy/<user_id>/<topic>/<subtopic>', methods=['GET'])
def get_subtopic_accuracy_data(user_id, topic, subtopic):
    """Get accuracy trend showing all attempts for specific subtopic"""
    from chart_data import generate_subtopic_accuracy_trend
    
    try:
        accuracy_data = generate_subtopic_accuracy_trend(user_id, topic, subtopic)
        return jsonify({
            'success': True,
            'accuracy_data': accuracy_data,
            'total_attempts': len(accuracy_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    USE_OLLAMA = os.getenv('USE_OLLAMA', 'false').lower() == 'true'

    ai_status = "groq" if GROQ_API_KEY else "ollama" if USE_OLLAMA else "unavailable"
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'ai_backend': ai_status,
        'version': 'FINAL-6.2-pure-ai'
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 LEARNING ANALYTICS API - FINAL VERSION")
    print("="*60)
    
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    USE_OLLAMA = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
    
    if USE_OLLAMA:
        print("✅ AI Backend: Ollama (Local)")
        print("   Ensure: ollama run llama3.1")
    elif GROQ_API_KEY:
        print("✅ AI Backend: Groq Cloud")
        print("   Status: Configured")
    else:
        print("❌ AI Backend: NOT CONFIGURED")
        print("   ⚠️  Add GROQ_API_KEY to .env file")
        print("   📝 Example: GROQ_API_KEY=gsk_xxxxx")
    
    print(f"\n🌐 Server: http://localhost:5000")
    print(f"📊 Dashboard: http://localhost:5000")
    print(f"💚 Health: http://localhost:5000/health")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)