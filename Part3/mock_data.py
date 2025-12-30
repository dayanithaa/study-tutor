# mockdata 
users = [
    {
        "id": "user_001",
        "name": "Alex Johnson",
        "email": "alex@example.com",
        "joinedDate": "2024-01-15",
        "topics": {
            "algebra": {
                "name": "Algebra",
                "prerequisites": [],
                "subtopics": {
                    "Linear Equations": {
                        "assessments": [
                            {
                                "assessment_id": "alg_lin_01",
                                "date": "2024-11-25",
                                "scores": {
                                    "intuition": 65,
                                    "memory": 70,
                                    "application": 60
                                },
                                "questions": [
                                    {
                                        "id": "alg_lin_q1",
                                        "dimension": "application",
                                        "question": "Solve: 2x + 3 = 7",
                                        "options": ["x=2", "x=1", "x=3", "x=4"],
                                        "correctOption": 0,
                                        "userOption": 0
                                    },
                                    {
                                        "id": "alg_lin_q2",
                                        "dimension": "intuition",
                                        "question": "What does the coefficient represent?",
                                        "options": ["Rate of change", "Y-intercept", "Constant", "Variable"],
                                        "correctOption": 0,
                                        "userOption": 2
                                    }
                                ]
                            }
                        ]
                    },
                    "Quadratic Equations": {
                        "assessments": [
                            {
                                "assessment_id": "alg_quad_01",
                                "date": "2024-12-01",
                                "scores": {
                                    "intuition": 70,
                                    "memory": 85,
                                    "application": 75
                                },
                                "questions": [
                                    {
                                        "id": "alg_quad_q1",
                                        "dimension": "application",
                                        "question": "Solve: x² - 5x + 6 = 0",
                                        "options": ["x = 2, 3", "x = -2, -3", "x = 1, 6", "x = -1, -6"],
                                        "correctOption": 0,
                                        "userOption": 0
                                    },
                                    {
                                        "id": "alg_quad_q2",
                                        "dimension": "memory",
                                        "question": "Quadratic formula: x = ?",
                                        "options": ["-b ± √(b²-4ac) / 2a", "-b / 2a", "b² - 4ac", "ax² + bx + c"],
                                        "correctOption": 0,
                                        "userOption": 0
                                    }
                                ]
                            },
                            {
                                "assessment_id": "alg_quad_02",
                                "date": "2024-12-20",
                                "scores": {
                                    "intuition": 80,
                                    "memory": 90,
                                    "application": 85
                                },
                                "questions": [
                                    {
                                        "id": "alg_quad_q3",
                                        "dimension": "memory",
                                        "question": "What is the discriminant of x² + 4x + 4?",
                                        "options": ["0", "4", "8", "16"],
                                        "correctOption": 0,
                                        "userOption": 0
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            "geometry": {
                "name": "Geometry",
                "prerequisites": ["algebra"],
                "subtopics": {
                    "Triangles": {
                        "assessments": [
                            {
                                "assessment_id": "geo_tri_01",
                                "date": "2024-12-05",
                                "scores": {
                                    "intuition": 75,
                                    "memory": 70,
                                    "application": 65
                                },
                                "questions": [
                                    {
                                        "id": "geo_tri_q1",
                                        "dimension": "intuition",
                                        "question": "What is the sum of interior angles of a triangle?",
                                        "options": ["90°", "180°", "270°", "360°"],
                                        "correctOption": 1,
                                        "userOption": 1
                                    },
                                    {
                                        "id": "geo_tri_q2",
                                        "dimension": "application",
                                        "question": "Find the third angle if two angles are 45° and 60°",
                                        "options": ["75°", "85°", "65°", "95°"],
                                        "correctOption": 0,
                                        "userOption": 1
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            "calculus": {
                "name": "Calculus",
                "prerequisites": ["algebra", "trigonometry"],
                "subtopics": {
                    "Limits": {
                        "assessments": [
                            {
                                "assessment_id": "calc_lim_01",
                                "date": "2024-12-10",
                                "scores": {
                                    "intuition": 70,
                                    "memory": 80,
                                    "application": 35
                                },
                                "questions": [
                                    {
                                        "id": "calc_lim_q1",
                                        "dimension": "intuition",
                                        "question": "What does a limit describe?",
                                        "options": ["Exact value", "Approaching behavior", "Maximum value", "Undefined point"],
                                        "correctOption": 1,
                                        "userOption": 1
                                    },
                                    {
                                        "id": "calc_lim_q2",
                                        "dimension": "application",
                                        "question": "Evaluate: lim(x→2) (x² - 4)/(x - 2)",
                                        "options": ["0", "2", "4", "undefined"],
                                        "correctOption": 2,
                                        "userOption": 0
                                    },
                                    {
                                        "id": "calc_lim_q3",
                                        "dimension": "application",
                                        "question": "Using L'Hôpital's rule, evaluate: lim(x→0) sin(x)/x",
                                        "options": ["0", "1", "∞", "undefined"],
                                        "correctOption": 1,
                                        "userOption": 0
                                    }
                                ]
                            },
                            {
                                "assessment_id": "calc_lim_02",
                                "date": "2024-12-22",
                                "scores": {
                                    "intuition": 80,
                                    "memory": 90,
                                    "application": 45
                                },
                                "questions": [
                                    {
                                        "id": "calc_lim_q4",
                                        "dimension": "application",
                                        "question": "Which concept defines instantaneous rate of change?",
                                        "options": ["Continuity", "Average rate", "Derivative via limits", "Asymptote"],
                                        "correctOption": 2,
                                        "userOption": 0
                                    },
                                    {
                                        "id": "calc_lim_q5",
                                        "dimension": "application",
                                        "question": "Evaluate: lim(x→0) (e^x - 1)/x",
                                        "options": ["0", "1", "e", "undefined"],
                                        "correctOption": 1,
                                        "userOption": 2
                                    }
                                ]
                            }
                        ]
                    },
                    "Derivatives": {
                        "assessments": [
                            {
                                "assessment_id": "calc_der_01",
                                "date": "2024-12-15",
                                "scores": {
                                    "intuition": 40,
                                    "memory": 60,
                                    "application": 50
                                },
                                "questions": [
                                    {
                                        "id": "calc_der_q1",
                                        "dimension": "intuition",
                                        "question": "Geometrically, what does a derivative represent?",
                                        "options": ["Area under curve", "Slope of tangent", "Total distance", "Volume"],
                                        "correctOption": 1,
                                        "userOption": 0
                                    },
                                    {
                                        "id": "calc_der_q2",
                                        "dimension": "application",
                                        "question": "Find d/dx(x³)",
                                        "options": ["x²", "2x²", "3x²", "3x"],
                                        "correctOption": 2,
                                        "userOption": 1
                                    },
                                    {
                                        "id": "calc_der_q3",
                                        "dimension": "application",
                                        "question": "Find d/dx(sin(x))",
                                        "options": ["cos(x)", "-cos(x)", "sin(x)", "-sin(x)"],
                                        "correctOption": 0,
                                        "userOption": 2
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            "probability": {
                "name": "Probability",
                "prerequisites": ["statistics"],
                "subtopics": {
                    "Bayes Theorem": {
                        "assessments": [
                            {
                                "assessment_id": "prob_bayes_01",
                                "date": "2024-12-18",
                                "scores": {
                                    "intuition": 30,
                                    "memory": 40,
                                    "application": 25
                                },
                                "questions": [
                                    {
                                        "id": "prob_bayes_q1",
                                        "dimension": "memory",
                                        "question": "What is the correct formula for P(A|B)?",
                                        "options": ["P(A)P(B)", "P(B|A)P(B)", "P(B|A)P(A)/P(B)", "P(A)/P(B)"],
                                        "correctOption": 2,
                                        "userOption": 1
                                    },
                                    {
                                        "id": "prob_bayes_q2",
                                        "dimension": "intuition",
                                        "question": "What does Bayes' Theorem help us update?",
                                        "options": ["Prior probability", "Posterior probability", "Likelihood", "Evidence"],
                                        "correctOption": 1,
                                        "userOption": 0
                                    },
                                    {
                                        "id": "prob_bayes_q3",
                                        "dimension": "application",
                                        "question": "If P(Disease)=0.01, P(+|Disease)=0.9, P(+|No Disease)=0.1, what is P(Disease|+)?",
                                        "options": ["0.01", "0.09", "0.083", "0.9"],
                                        "correctOption": 2,
                                        "userOption": 0
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
    },
    

    {
        "id": "user_003",
        "name": "New Student",
        "email": "new@example.com",
        "joinedDate": "2024-12-22",
        "topics": {}
    }
]

def get_user_by_id(user_id: str):
    """Retrieve user data by ID"""
    for user in users:
        if user["id"] == user_id:
            return user
    return None