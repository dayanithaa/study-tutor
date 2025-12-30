
Learning-Analytics-Personalized Feedback

A Flask-based AI platform that tracks student performance across Intuition, Memory, and Application dimensions and provides personalized feedback.
The platform analyses users performance and gives scores for all topics 
It uses Uses LLMs (OpenAI/Groq) to generate personalized AI feedback for users based on their performance in that topics.
The Platform acts as a human tutor who knows about the user (in our cases it goes through users data and the feedback history it has provided)
It also generates actions to be taken with priority

Tech Stack used
Backend: Python 3, Flask, SQLAlchemy 

Frontend: HTML5, CSS3, JavaScript, Chart.js

Database: SQLite (SQLAlchemy ORM)

AI: OpenAI API / Groq


The platform generates charts to visualize a student's profile, tracks learning consistency, and monitor performance over time with different charts


Process to run the Application
1 Install Python

2 Set Up a Virtual Environment

3 Install Dependencies: pip install -r requirements.txt

4 Configure Environment: Create .env file with keys.

5 Initialize Database: python init_db.py ( to get the user data)

6 Run Application: python app.py

7 Open Browser: http://localhost:5000

