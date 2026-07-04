#!/bin/bash
#Bot
python bot.py &

#FastAPI
uvicorn main:app --host 0.0.0.0 --port $PORT
