# Study Tutor Platform 

A  web application that extracts concepts from academic documents and visualizes them as interactive knowledge graphs, quizes the user and sends back feed back to help .

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

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start MongoDB**
   ```bash
   # Make sure MongoDB is running on localhost:27017
   ```

3. **Run the Application**
   ```bash
   python app.py
   ```
   Or use the provided batch file:
   ```bash
   start_and_open.bat
   ```

4. **Access the App**
Open http://localhost:8000 in your browser
Create an account or sign in
Upload documents and explore the knowledge graphs

 -Project Structure

```
├── app.py              # Main FastAPI application
├── config.py           # Configuration settings
├── database.py         # Database utilities
├── requirements.txt    # Python dependencies
├── static/
│   └── index.html     # Frontend interface
└── uploads/           # Document storage
```

-Usage

1. **Sign Up**: Create a new account with email and password
2. **Upload**: Drop PDF or PowerPoint files into the upload area
3. **Process**: The system extracts concepts and relationships automatically
4. **Visualize**: View interactive knowledge graphs with different layouts
5. **Explore**: Click nodes to see concept details and relationships

## Configuration

Update `config.py` to customize:
- Database connection string
- JWT secret key (change in production!)
- File upload limits
- Token expiration time

## Development

The application uses:
- FastAPI for the REST API
- MongoDB for document and user storage
- Advanced PDF processing with concept extraction
- Interactive graph visualization with multiple layout algorithms

## Security Notes

- Change the `SECRET_KEY` in production
- Use environment variables for sensitive configuration
- The app includes CORS middleware for development

---

*Built with FastAPI and modern web technologies for intelligent document analysis.*


Part 3

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

5 Initialize Database: python init_db.py ( to get the user data )

6 Run Application: python app.py

7 Open Browser: http://localhost:5000
