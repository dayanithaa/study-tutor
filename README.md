# Study Tutor Platform 

A web application that analyzes academic documents, extracts key concepts, and visualizes them as interactive knowledge graphs. The platform assesses user understanding through adaptive quizzes and provides personalized feedback to support learning and improvement.
## Part 1

Document Upload: Support for PDF, PowerPoint, and ZIP files
PDF text extraction and concept identification
Knowledge Graphs: Interactive visualization of concepts and their relationships
User Authentication: Secure signup/login with JWT tokens

- Tech Stack

Backend: FastAPI (Python)
Database: MongoDB
Frontend: Vanilla HTML/CSS/JavaScript
Graph Visualization: Cytoscape.js
PDF Processing: PyMuPDF, pdfplumber
Authentication: JWT with bcrypt password hashing

- Quick Start

1. pip install -r requirements.txt
2. Start MongoDB
3.  python app.py
   Or 
   start_and_open.bat
Open http://localhost:8000 in your browser
Create an account or sign in
Upload documents and explore the knowledge graphs


- Usage

1. Sign Up: Create a new account with email and password
2. Upload: Drop PDF or PowerPoint files into the upload area
3. Process: The system extracts concepts and relationships automatically
4. Visualize: View interactive knowledge graphs with different layouts
5. Explore: Click nodes to see concept details and relationships




## Part 3

A Flask-based AI platform that tracks student performance across Intuition, Memory, and Application dimensions and provides personalized feedback based on the user assessment data from part2.
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

## FUTURE IMPROVEMENTS:
Integration
5 Initialize Database: python init_db.py ( to get the user data )

6 Run Application: python app.py

7 Open Browser: http://localhost:5000
