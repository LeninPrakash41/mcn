@echo off
echo Installing Flask dependencies...
pip install -r requirements.txt

echo Starting MCN Web Playground...
python server.py

pause
