from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List
import requests
from bs4 import BeautifulSoup
import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv
from types import SimpleNamespace
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

app = FastAPI(title="n8n Python Tools", version="1.0.0")

# --- Configuration ---
# Restrict file operations to this directory for safety
SAFE_FILE_DIR = os.path.join(os.getcwd(), "file_storage")
if not os.path.exists(SAFE_FILE_DIR):
    os.makedirs(SAFE_FILE_DIR)

# --- Models ---
class CrawlRequest(BaseModel):
    url: str
    selector: Optional[str] = None # CSS selector to extract specific content
    cookie: str

class TextProcessRequest(BaseModel):
    text: str
    operation: str # 'uppercase', 'lowercase', 'word_count'

class FileWriteRequest(BaseModel):
    filename: str
    content: str

class LoginRequest(BaseModel):
    url: str
    username: str
    password: str

class AssignmentsRequest(BaseModel):
    course: str
    cookie: str
    
class AssignmentRequest(BaseModel):
    assignment_id: str
    cookie: str

class gemini_response_schema(BaseModel):
	score: int
	reason: str
# --- Endpoints ---

@app.get("/")
def read_root():
    return {"status": "online", "docs_url": "http://localhost:8000/docs"}

@app.post("/tools/crawl")
def crawl_website(request: CrawlRequest):
    """
    Fetches a URL and returns the text content. 
    Optionally accepts a CSS selector to filter the result.
    """
    try:
        headers = {'cookie':request.cookie}
        response = requests.get(request.url, verify=False, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if request.selector:
            # Extract specific elements
            elements = soup.select(request.selector)
            content = "\n".join([el.get_text(strip=True) for el in elements])
        else:
            # Extract all text
            content = soup.get_text(strip=True)
            
        return {
            "url": request.url,
            "status_code": response.status_code,
            "content": content[:5000], # Limit response size for n8n
            "title": soup.title.string if soup.title else ""
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/text-process")
def process_text(request: TextProcessRequest):
    """
    Performs simple operations on text.
    Operations: 'uppercase', 'lowercase', 'word_count', 'reverse'
    """
    op = request.operation.lower()
    result = ""
    
    if op == "uppercase":
        result = request.text.upper()
    elif op == "lowercase":
        result = request.text.lower()
    elif op == "word_count":
        result = str(len(request.text.split()))
    elif op == "reverse":
        result = request.text[::-1]
    else:
        return {"error": f"Unknown operation: {op}"}
        
    return {"original": request.text, "operation": op, "result": result}

@app.post("/tools/file/write")
def write_file(request: FileWriteRequest):
    """
    Writes content to a file in the safe storage directory.
    """
    # Security: Prevent directory traversal
    if ".." in request.filename or "/" in request.filename or "\\" in request.filename:
         raise HTTPException(status_code=400, detail="Invalid filename. Use simple filenames only.")
         
    file_path = os.path.join(SAFE_FILE_DIR, request.filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(request.content)
        
    return {"status": "success", "file_path": file_path, "size": len(request.content)}

@app.get("/tools/file/list")
def list_files():
    """
    Lists files in the storage directory.
    """
    files = os.listdir(SAFE_FILE_DIR)
    return {"files": files, "count": len(files)}

@app.post("/tools/moodle-login-helper")
def moodle_login(request: LoginRequest):
    """
    Simulates a login request to capture a session token or cookie.
    Useful for Moodle or other form-based auth sites.
    """
    try:
        session = requests.Session()
        # This is a generic example. Moodle specifically often requires extracting a 'logintoken' first.
        # Step 1: Get the login page to find tokens (if needed)
        login_page = session.get(request.url, verify=False)
        
        # Step 2: Post credentials
        soup = BeautifulSoup(login_page.text, 'html.parser')
        logintoken = soup.find('form').find('input',attrs={"name":"logintoken"}).get('value')

        payload = {
            "username": request.username,
            "password": request.password,
            "logintoken": logintoken,
            "anchor": '',
        }
        
        # Note: Moodle's actual login URL is usually /login/index.php
        response = session.post(request.url, data=payload, verify=False)
        cookie = "; ".join([f"{x.name}={x.value}" for x in session.cookies])
        return {
            "status": response.status_code,
            "cookie": cookie,
            "url_after_login": response.url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/get-assinments-of-class")
def get_assignments(request: AssignmentsRequest):
    try:
        headers = {'cookie':request.cookie}
        courses_response = requests.get('https://moodle.nhu.edu.tw/my/courses.php', verify=False, headers=headers)
        soup = BeautifulSoup(courses_response.text, 'html.parser')
        selector = f'a[href*="/course/view.php?id="]:-soup-contains("{request.course}")'
        matches = soup.select(selector)
        course = matches[0]
        course_url = course['href']
        
        course_response = requests.get('https://moodle.nhu.edu.tw' + course_url, verify=False, headers=headers)
        soup = BeautifulSoup(course_response.text, 'html.parser')
        selector = 'a[href*="/assign/view.php?id="]'
        assignments = soup.select(selector)
        
        results = []
        for assignment in assignments:
            # 1. Extract the ID from the href (e.g., id=13041)
            href = assignment.get('href')
            id_match = re.search(r'id=(\d+)', href)
            if id_match:
                course_id = id_match.group(1)
                
                # 2. Extract the Name
                # We find the 'instancename' span
                name_span = assignment.find('span', class_='instancename')
                
                if name_span:
                    
                    # Get the clean text
                    course_name = name_span.get_text(strip=True)
                    
                    # 3. Add to list
                    results.append({
                        "id": course_id,
                        "name": course_name
                    })
        # 4. Convert to JSON format
        json_output = json.dumps(results, ensure_ascii=False)
        
        return {
            "status": course_response.status_code,
            "title": soup.title.string if soup.title else "",
            "assignments": json_output
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))        

@app.post("/tools/get-assinment-info")
def get_assignment_info(request: AssignmentRequest):
    try:
        headers = {'cookie':request.cookie}
        selector = '#intro .no-overflow'
        description_response = requests.get(f'https://moodle.nhu.edu.tw/mod/assign/view.php?id={request.assignment_id}', verify=False, headers=headers)
        soup = BeautifulSoup(description_response.text, 'html.parser')
        requirements = soup.select(selector)[0]
        requirements = requirements.get_text(separator="\n", strip=True)
        assignment_response = requests.get(f'https://moodle.nhu.edu.tw/mod/assign/view.php?id={request.assignment_id}&action=grading', verify=False, headers=headers)
        soup = BeautifulSoup(assignment_response.text, 'html.parser')
        selector = 'tr[id*="mod_assign_grading"]'
        rows = soup.select(selector)
        results = []
        for user_row in rows:
            user = user_row.select('a[href*="/user/"][id*="action"]')[0].text.split(' ')
            graded = True if not user_row.select('div[class="submissionstatussubmitted"]') else False
            score = user_row.select('input[class*="quickgrade"]')[0].get('value')
            score = score if not score else '0'
            files = [{"filename":file.get_text(),"url":file['href']} for file in user_row.select('a[target="_blank"]')]
            
            results.append({
                "id": user.pop(),
                "name": ' '.join(user),
                "score": score,
                "files": files,
            })
        # 4. Convert to JSON format
        json_output = json.dumps(results, ensure_ascii=False)
        
        return {
            "status": assignment_response.status_code,
            "title": soup.title.string if soup.title else "",
            "requirements":requirements,
            "assignments": json_output
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))        

@app.post("/tools/score-assignment")
def score_assignment(request: AssignmentRequest):
    try:
        headers = {'cookie':request.cookie}
        selector = '#intro .no-overflow'
        description_response = requests.get(f'https://moodle.nhu.edu.tw/mod/assign/view.php?id={request.assignment_id}', verify=False, headers=headers)
        soup = BeautifulSoup(description_response.text, 'html.parser')
        requirements = soup.select(selector)[0]
        requirements = requirements.get_text(separator="\n", strip=True)
        assignment_response = requests.get(f'https://moodle.nhu.edu.tw/mod/assign/view.php?id={request.assignment_id}&action=grading', verify=False, headers=headers)
        soup = BeautifulSoup(assignment_response.text, 'html.parser')
        selector = 'tr[id*="mod_assign_grading"]'
        rows = soup.select(selector)
        results = []
        for user_row in rows:

            user = user_row.select('a[href*="/user/"][id*="action"]')[0].text.split(' ')
            graded = True if not user_row.select('div[class="submissionstatussubmitted"]') else False
            score = user_row.select('input[class*="quickgrade"]')[0].get('value')
            score = score if not score else '0'
            files = [{"filename":file.get_text(),"url":file['href']} for file in user_row.select('a[target="_blank"]')]
            answer = requests.get(files[0]['url'], headers=headers,verify=False) if len(files) and 'cpp' in files[0]['url'] else ''
            
            if answer:
                contents = {
                    "title": soup.title.string if soup.title else "",
                    "requirements":requirements,
                    "answer": answer.text
                }
                contents = json.dumps(contents, ensure_ascii=False)
                client = genai.Client(api_key=GEMINI_API_KEY)
                response = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents= contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=gemini_response_schema,
                        system_instruction="You are an assistant helping teacher score assignment according to requirements. Score is 0-100. Keep reason simple.",
                    )
                )
            else:
                response = SimpleNamespace(
                    parsed=SimpleNamespace(
                        score=0,
                        reason="No answer submitted or Wrong file format"
                    )
                )
            response.parsed
            results.append({
                "id": user.pop(),
                "name": ' '.join(user),
                "score": response.parsed.score,
                "reason": response.parsed.reason,
            })

        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))        