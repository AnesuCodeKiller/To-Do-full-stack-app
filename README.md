1. Features
 1.1 Backend (Python 3)
●  REST API with Flask or FastAPI (Python 3.8+):
 	○  POST /register: Create user accounts with secure credential storage.
            ○  POST /login: Authenticate users and return a mock JWT or token.
            ○  GET /protected: Verify token authenticity.
●  Secure endpoints with Authorization: Bearer header.
●  Log requests and errors to app.log using Python's logging module.
●  Enable CORS for localhost:3000.
 								
1.2 Frontend (React + TypeScript)
●  Single-page React 18+ app with TypeScript:
 	○  Registration and Login Pages: Forms for POST /register and POST
 	/login, store the token, and redirect to a protected route.
            ○  Protected Route: A page for authenticated users, with verification via GET
 	/protected.
 									
        ○  Logout: Clear the token and redirect to the login page.
●  Use useState, useEffect, and strict TypeScript typing (no any).
●  Show loading states (e.g., a spinner) and errors (e.g., "Invalid credentials").
●  Apply minimal, responsive styling with CSS or Tailwind.
 								
1.3 Integration
							
●  Connect the frontend to the backend using fetch or Axios.			●  Include the authentication token in headers for all protected endpoints.
●  Handle async operations and errors (e.g., a 401 status for invalid tokens). 
