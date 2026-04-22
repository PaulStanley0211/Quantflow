@echo off
cd /d "c:\Users\pauls\Morning_briefing_Agent"
".venv\Scripts\python.exe" -u briefing_agent_once.py >> logs\briefing.log 2>&1
