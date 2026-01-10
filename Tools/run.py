import uvicorn

if __name__ == "__main__":
    # Reload=True allows you to change code and see updates instantly without restarting
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
