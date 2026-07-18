# This script starts both the backend and frontend simultaneously

Write-Host "Starting Backend..."
$backend = Start-Process -FilePath "powershell" -ArgumentList "-Command `"cd backend; `$env:PYTHONIOENCODING='utf-8'; .\`".venv\Scripts\python.exe`" -m uvicorn main:app --port 8000 --reload`"" -PassThru

Write-Host "Starting Frontend..."
$frontend = Start-Process -FilePath "powershell" -ArgumentList "-Command `"cd frontend; npm run dev`"" -PassThru

Write-Host "Both servers are starting!"
Write-Host "Backend is running on http://127.0.0.1:8000"
Write-Host "Frontend is running on http://localhost:3000"
Write-Host "Close those terminal windows to stop the servers."
