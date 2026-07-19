# Entry point for Streamlit Community Cloud
# Streamlit Cloud looks for streamlit_app.py in the repo root
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from app.main import main
main()
