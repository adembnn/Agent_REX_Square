@echo off
REM Lanceur de l'agent REX (interface Streamlit) accessible sur le reseau interne.
cd /d "%~dp0"
echo ============================================================
echo   Agent REX - Square Management
echo   Local        : http://localhost:8501
echo   Reseau (LAN) : http://%COMPUTERNAME%:8501  (ou http://[ton-IP]:8501)
echo   Ctrl+C pour arreter.
echo ============================================================
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
pause
