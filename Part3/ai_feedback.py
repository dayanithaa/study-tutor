
import os
import requests
from datetime import datetime

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
USE_OLLAMA = os.environ.get('USE_OLLAMA', 'false').lower() == 'true'

# Debug logging
print(f"🔧 AI CONFIG CHECK:")
print(f"   GROQ_API_KEY: {'SET' if GROQ_API_KEY else 'NOT SET'}")
print(f"   USE_OLLAMA: {USE_OLLAMA}")


def call_groq_api(prompt, max_tokens=2000):
    """Call Groq API with error logging"""
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY not found in environment")
        return None
    
    try:
        print(f"📡 Calling Groq API (key starts: {GROQ_API_KEY[:10]}...)")
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert learning coach analyzing student performance data. Speak directly to the student using 'you' and 'your'. Analyze their actual mistakes to find patterns and give specific, actionable advice."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": max_tokens
            },
            timeout=60
        )
        
        print(f"📡 Groq response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()['choices'][0]['message']['content']
            print(f"✅ Groq API success - response length: {len(result)}")
            return result
        else:
            print(f"❌ Groq API error: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Groq API exception: {e}")
        import traceback
        traceback.print_exc()
        return None


def call_ollama_api(prompt, max_tokens=2000):
    """Call Ollama API with error logging"""
    try:
        print(f"🖥️ Calling Ollama API...")
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": max_tokens}
            },
            timeout=60
        )
        
        print(f"🖥️ Ollama response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()['response']
            print(f"✅ Ollama API success - response length: {len(result)}")
            return result
        else:
            print(f"❌ Ollama API error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Ollama API exception: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_ai_feedback(user_data, analytics, subtopic=None, topic=None):
    """
    Generate AI feedback - MUST use AI, NO fallback
    """
    from database import store_feedback, get_feedback_history, SessionLocal, Assessment
    
    user_id = user_data['id']
    user_name = user_data['name']
    
    print(f"\n{'='*60}")
    print(f"🤖 GENERATING AI FEEDBACK")
    print(f"   User: {user_name} ({user_id})")
    print(f"   Topic: {topic or 'All'}")
    print(f"   Subtopic: {subtopic or 'All'}")
    print(f"{'='*60}")
    
    # Check AI configuration
    if not GROQ_API_KEY and not USE_OLLAMA:
        print("❌ NO AI BACKEND CONFIGURED!")
        return {
            'summary': '⚠️ AI service not configured. Add GROQ_API_KEY to .env file or set USE_OLLAMA=true',
            'recommendations': [
                'Get Groq API key from https://console.groq.com',
                'Add GROQ_API_KEY=your_key to .env file',
                'Or install Ollama and set USE_OLLAMA=true',
                'Restart the server after configuration'
            ],
            'actionItems': [{
                'id': 'config_ai',
                'description': '🔧 Configure AI backend in .env file',
                'topic': 'System',
                'priority': 'high',
                'estimatedTime': '5 minutes',
                'dueDate': 'Now',
                'type': 'configuration',
                'ai_error': True
            }],
            'ai_error': True,
            'error_type': 'not_configured',
            'timestamp': datetime.now().isoformat()
        }
    
    # Get assessment data
    db = SessionLocal()
    try:
        if subtopic:
            assessments = db.query(Assessment).filter(
                Assessment.user_id == user_id,
                Assessment.subtopic == subtopic
            ).order_by(Assessment.assessment_date.asc()).all()
            focus_area = subtopic
            
        elif topic:
            assessments = db.query(Assessment).filter(
                Assessment.user_id == user_id,
                Assessment.topic == topic
            ).order_by(Assessment.assessment_date.asc()).all()
            focus_area = topic
            
        else:
            assessments = db.query(Assessment).filter(
                Assessment.user_id == user_id
            ).order_by(Assessment.assessment_date.asc()).limit(30).all()
            focus_area = "overall performance"
        
        print(f"📊 Found {len(assessments)} assessments for {focus_area}")
        
        if not assessments:
            print(f"⚠️ No assessment data for {focus_area}")
            return {
                'summary': f'No assessment data for {focus_area}. Complete some assessments first!',
                'recommendations': [
                    f'Take assessments in {focus_area}',
                    'Practice the fundamentals',
                    'Return for AI feedback after completing assessments'
                ],
                'actionItems': [{
                    'id': 'no_data',
                    'description': f'📝 Complete assessments in {focus_area}',
                    'topic': focus_area,
                    'priority': 'high',
                    'estimatedTime': '30 minutes',
                    'dueDate': 'This week',
                    'type': 'assessment_needed'
                }],
                'ai_error': True,
                'error_type': 'no_data',
                'timestamp': datetime.now().isoformat()
            }
        
        # Extract mistakes
        all_mistakes = []
        performance_data = []
        
        for assessment in assessments:
            avg_score = (assessment.intuition_score + assessment.memory_score + assessment.application_score) / 3
            
            performance_data.append({
                'date': assessment.assessment_date.strftime('%Y-%m-%d'),
                'intuition': assessment.intuition_score,
                'memory': assessment.memory_score,
                'application': assessment.application_score,
                'avg': round(avg_score, 1)
            })
            
            questions = assessment.questions_data or []
            for q in questions:
                if q.get('userOption') != q.get('correctOption'):
                    options = q.get('options', [])
                    all_mistakes.append({
                        'date': assessment.assessment_date.strftime('%Y-%m-%d'),
                        'dimension': q.get('dimension', 'unknown'),
                        'question': q.get('question', '')[:150],
                        'your_answer': options[q['userOption']] if q.get('userOption') < len(options) else 'Unknown',
                        'correct_answer': options[q['correctOption']] if q.get('correctOption') < len(options) else 'Unknown'
                    })
        
        print(f"❌ Found {len(all_mistakes)} mistakes")
        
        # Get previous feedback
        previous_feedback = get_feedback_history(user_id, limit=3, subtopic=subtopic)
        print(f"📜 Found {len(previous_feedback)} previous feedback entries")
        
    finally:
        db.close()
    
    # Build AI prompt
    prompt = _build_ai_prompt(user_name, focus_area, performance_data, all_mistakes, previous_feedback)
    print(f"📝 Prompt length: {len(prompt)} characters")
    

    print(f"\n🚀 CALLING AI BACKEND...")
    response = None
    ai_backend = None
    
    if GROQ_API_KEY:
        print("   Using: Groq API")
        response = call_groq_api(prompt, max_tokens=2000)
        if response:
            ai_backend = "groq"
            print("   ✅ Groq succeeded")
        else:
            print("   ❌ Groq failed")
    
    if not response and USE_OLLAMA:
        print("   Using: Ollama")
        response = call_ollama_api(prompt, max_tokens=2000)
        if response:
            ai_backend = "ollama"
            print("   ✅ Ollama succeeded")
        else:
            print("   ❌ Ollama failed")
    
    # Check if AI actually worked
    if not response or not ai_backend:
        print("\n❌ ALL AI BACKENDS FAILED")
        return {
            'summary': '❌ AI service failed to respond. Please check configuration and try again.',
            'recommendations': [
                'Verify GROQ_API_KEY is correct in .env file',
                'Check internet connection for Groq API',
                'Or ensure Ollama is running: ollama run llama3.1',
                'Check server logs for detailed error messages'
            ],
            'actionItems': [{
                'id': 'ai_failed',
                'description': '🔄 Try again - AI service temporarily unavailable',
                'topic': focus_area,
                'priority': 'high',
                'estimatedTime': 'Retry now',
                'dueDate': 'Immediate',
                'type': 'retry',
                'ai_error': True
            }],
            'ai_error': True,
            'error_type': 'ai_failed',
            'timestamp': datetime.now().isoformat()
        }
    
    print(f"✅ AI RESPONSE RECEIVED")
    print(f"   Backend: {ai_backend}")
    print(f"   Length: {len(response)} chars")
    
    # Parse response
    feedback = {
        'timestamp': datetime.now().isoformat(),
        'ai_powered': True,
        'ai_backend': ai_backend,
        'focus_area': focus_area,
        'total_assessments': len(performance_data),
        'total_mistakes_analyzed': len(all_mistakes),
        'summary': _extract_summary(response),
        'recommendations': _extract_recommendations(response),
        'actionItems': _extract_action_items(response, focus_area),
        'target_topic': topic,
        'target_subtopic': subtopic,
        'raw_ai_response': response
    }
    
    # Store feedback
    store_feedback(user_id, feedback, subtopic)
    print(f"💾 Feedback stored")
    print(f"{'='*60}\n")
    
    return feedback


def _build_ai_prompt(user_name, focus_area, performance_data, all_mistakes, previous_feedback):
    """Build AI prompt"""
    
    # Performance
    if performance_data:
        latest = performance_data[-1]
        first = performance_data[0]
        perf_text = f"""PERFORMANCE ({len(performance_data)} assessments):
Latest: {latest['date']} - I:{latest['intuition']}% M:{latest['memory']}% A:{latest['application']}% (Avg: {latest['avg']}%)
First: {first['date']} - I:{first['intuition']}% M:{first['memory']}% A:{first['application']}% (Avg: {first['avg']}%)
Progress: {latest['avg'] - first['avg']:+.1f}%"""
    else:
        perf_text = "No performance data"
    
    # Mistakes
    mistakes_text = f"MISTAKES ({len(all_mistakes)} total):\n"
    if all_mistakes:
        by_dim = {}
        for m in all_mistakes:
            dim = m['dimension']
            if dim not in by_dim:
                by_dim[dim] = []
            by_dim[dim].append(m)
        
        for dim, mistakes in by_dim.items():
            mistakes_text += f"\n{dim.upper()} ({len(mistakes)}):\n"
            for m in mistakes[:5]:
                mistakes_text += f"  • {m['question'][:80]}...\n"
                mistakes_text += f"    You: {m['your_answer']}, Correct: {m['correct_answer']}\n"
    else:
        mistakes_text += "No mistakes - excellent!"
    
    # Previous feedback
    feedback_text = ""
    if previous_feedback:
        feedback_text = "\nPREVIOUS FEEDBACK:\n"
        for fb in previous_feedback[:2]:
            feedback_text += f"  • {fb.get('summary', '')[:80]}...\n"
    
    prompt = f"""Coach {user_name} on {focus_area}.

{perf_text}

{mistakes_text}
{feedback_text}

Give {user_name}:
1. Current level (2 sentences)
2. Mistake patterns (3 points from their actual errors)
3. Actions (4 specific items based on mistakes)
4. Practice time this week

Use "you" and "your". Be specific about their mistakes."""

    return prompt


def _extract_summary(response):
    """Extract summary"""
    lines = [l.strip() for l in response.split('\n') if l.strip()]
    for line in lines[:10]:
        if len(line) > 50 and not line.startswith(('#', '-', '•', '*', '1', '2', '3')):
            return line.replace('**', '').strip()
    return response[:300].replace('**', '').strip()


def _extract_recommendations(response):
    """Extract recommendations"""
    recommendations = []
    lines = response.split('\n')
    
    for line in lines:
        line = line.strip()
        if line and (line.startswith(('-', '•', '*')) or (line and line[0].isdigit() and '. ' in line)):
            clean = line.lstrip('-•*0123456789.)]: ').strip().replace('**', '')
            if len(clean) > 20:
                recommendations.append(clean)
    
    return recommendations[:8]


def _extract_action_items(response, focus_area):
    """Extract action items - these are derived from recommendations, so don't show both"""
    recommendations = _extract_recommendations(response)
    
    action_items = []
    # Only take first 6 to avoid too many items
    for i, rec in enumerate(recommendations[:6]):
        priority = 'high' if i < 2 else 'medium' if i < 4 else 'low'
        action_items.append({
            'id': f"ai_{i+1}",
            'description': rec,
            'topic': focus_area,
            'priority': priority,
            'estimatedTime': 'This week' if priority == 'high' else '2 weeks',
            'dueDate': 'Next session' if priority == 'high' else 'Ongoing',
            'type': 'AI Generated',
            'ai_generated': True
        })
    
    return action_items


def generate_dashboard_action_items(user_id, user_name, analytics):
    """Generate dashboard action items - MUST use AI"""
    from database import SessionLocal, Assessment, get_feedback_history
    
    print(f"\n{'='*60}")
    print(f"🎯 GENERATING DASHBOARD ACTION ITEMS")
    print(f"   User: {user_name} ({user_id})")
    print(f"{'='*60}")
    
    # Check AI configuration
    if not GROQ_API_KEY and not USE_OLLAMA:
        print("❌ NO AI BACKEND CONFIGURED")
        return [{
            'id': 'config',
            'description': '🔧 Configure AI backend (GROQ_API_KEY in .env)',
            'topic': 'System',
            'priority': 'high',
            'estimatedTime': '5 min',
            'dueDate': 'Now',
            'type': 'config',
            'ai_error': True
        }]
    
    db = SessionLocal()
    try:
        recent_assessments = db.query(Assessment).filter(
            Assessment.user_id == user_id
        ).order_by(Assessment.assessment_date.desc()).limit(20).all()
        
        print(f"📊 Found {len(recent_assessments)} recent assessments")
        
        if not recent_assessments:
            print("⚠️ No assessment data")
            return [{
                'id': 'no_data',
                'description': '📚 Complete assessments to get AI action items',
                'topic': 'General',
                'priority': 'medium',
                'estimatedTime': '30 min',
                'dueDate': 'This week',
                'type': 'assessment_needed'
            }]
        
        # Analyze topics
        topic_perf = {}
        topic_mistakes = {}
        
        for assessment in recent_assessments:
            topic = assessment.topic
            avg = (assessment.intuition_score + assessment.memory_score + assessment.application_score) / 3
            
            if topic not in topic_perf:
                topic_perf[topic] = []
                topic_mistakes[topic] = []
            
            topic_perf[topic].append(avg)
            
            questions = assessment.questions_data or []
            for q in questions:
                if q.get('userOption') != q.get('correctOption'):
                    topic_mistakes[topic].append(q.get('dimension', 'unknown'))
        
        # Build prompt
        weak_topics = []
        for topic, scores in topic_perf.items():
            avg = sum(scores) / len(scores)
            if avg < 75:
                weak_topics.append({
                    'topic': topic,
                    'avg': round(avg, 1),
                    'mistakes': len(topic_mistakes.get(topic, []))
                })
        
        weak_topics.sort(key=lambda x: x['avg'])
        print(f"📉 Found {len(weak_topics)} weak topics")
        
        if not weak_topics:
            print("✅ All topics strong!")
            return [{
                'id': 'great',
                'description': '✅ Excellent work! All topics above 75%',
                'topic': 'General',
                'priority': 'low',
                'estimatedTime': 'Keep going',
                'dueDate': 'Ongoing',
                'type': 'encouragement'
            }]
        
        # Get previous feedback
        prev_feedback = get_feedback_history(user_id, limit=3)
        
        prompt = f"""Create 5-6 action items for {user_name}'s dashboard.

WEAK TOPICS:
{chr(10).join([f"• {t['topic']}: {t['avg']}% ({t['mistakes']} mistakes)" for t in weak_topics[:4]])}

Previous focus: {', '.join([fb.get('focus_area', '') for fb in prev_feedback[:2]])}

Give {user_name} 5-6 specific actions:
- Each ONE clear task
- Include topic name
- Most important first
- Be specific (not generic)

Format: - [action for specific topic]"""

        print(f"📝 Prompt length: {len(prompt)}")
        
        # Call AI
        print(f"🚀 Calling AI...")
        response = None
        
        if GROQ_API_KEY:
            print("   Using Groq")
            response = call_groq_api(prompt, max_tokens=1000)
        
        if not response and USE_OLLAMA:
            print("   Using Ollama")
            response = call_ollama_api(prompt, max_tokens=1000)
        
        if not response:
            print("❌ AI call failed")
            return [{
                'id': 'failed',
                'description': '🔄 Try again - AI temporarily unavailable',
                'topic': 'System',
                'priority': 'high',
                'estimatedTime': 'Retry',
                'dueDate': 'Now',
                'type': 'retry',
                'ai_error': True
            }]
        
        print(f"✅ AI response received: {len(response)} chars")
        
        # Parse
        action_items = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and line.startswith(('-', '•', '*')):
                clean = line.lstrip('-•* ').strip().replace('**', '')
                if len(clean) > 15:
                    topic_found = 'General'
                    for topic in topic_perf.keys():
                        if topic.lower() in clean.lower():
                            topic_found = topic
                            break
                    
                    priority = 'high' if len(action_items) < 2 else 'medium' if len(action_items) < 4 else 'low'
                    
                    action_items.append({
                        'id': f"dash_{len(action_items)+1}",
                        'description': clean,
                        'topic': topic_found,
                        'priority': priority,
                        'estimatedTime': 'This week' if priority == 'high' else '2 weeks',
                        'dueDate': 'Next session' if priority == 'high' else 'Ongoing',
                        'type': 'AI Generated',
                        'ai_generated': True
                    })
        
        print(f"✅ Generated {len(action_items)} action items")
        print(f"{'='*60}\n")
        
        return action_items[:6] if action_items else [{
            'id': 'fallback',
            'description': f'Focus on {weak_topics[0]["topic"]} - currently at {weak_topics[0]["avg"]}%',
            'topic': weak_topics[0]['topic'],
            'priority': 'high',
            'estimatedTime': 'This week',
            'dueDate': 'Next session',
            'type': 'generated'
        }]
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return [{
            'id': 'error',
            'description': f'Error: {str(e)[:50]}...',
            'topic': 'System',
            'priority': 'error',
            'type': 'error',
            'ai_error': True
        }]
    finally:
        db.close()