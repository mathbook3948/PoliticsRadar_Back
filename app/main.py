from datetime import datetime
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from database.database import NewsSQLModelDB, get_session, engine
from services.News import News
scheduler = AsyncIOScheduler()

class NewsAnalysis(BaseModel):
    issue: str
    importance: str
    keyword: str
    effects: List[str]

class NewsResponse(BaseModel):
    id: int
    issue: str
    importance: str
    keyword : str
    time: datetime
    effects: List[str]  # EffectResponse 대신 str 사용
    
class ServerState:
    def __init__(self):
        self.last_activity = datetime.now()
        self.is_running = False

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, db_news):
        return cls(
            id=db_news.id,
            issue=db_news.issue,
            importance=db_news.importance,
            keyword=db_news.keyword,
            time=db_news.time,
            effects=[effect.effect for effect in db_news.effects]  # 문자열 리스트로 변환
        )
        
async def keep_alive():
    print("Keep-alive check executed")
    try:
        with Session(engine) as session:
            _ = NewsSQLModelDB.get_news(session)
        server_state.last_activity = datetime.now()
    except Exception as e:
        print(f"Keep-alive check failed: {e}")

app = FastAPI()
server_state = ServerState()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

load_dotenv()
db = NewsSQLModelDB()

def get_completion():
    system_message = """
    Analyze the news and provide a JSON response describing current events in Korean, in this exact format. Focus on the most recent news (lower index numbers indicate more recent news):
    {
       "issue": "Current factual situation in one sentence (Korean, max 10 words)",
       "importance": "2-3 sentences explaining objective significance and context (Korean). Prioritize analyzing recent events (news_1, news_2, etc.)", 
       "keyword": "Keyword (Korean) (IMPORTANT Only One Keyword)",
       "effects": [
           "Currently confirmed effect 1 (Korean)",
           "Currently confirmed effect 2 (Korean)",
           "Currently confirmed effect 3 (Korean)" 
       ]
    }

    Note: news_1 is the most recent, followed by news_2, news_3, etc. Give more weight to lower-numbered news items as they are more recent."""

    n = News()
    news = n.get()

    completion = requests.post(
        url='https://api.openai.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {os.getenv("OPENAI_API_KEY")}'},
        json={
            'model': 'gpt-4o-mini',
            'messages': [
                {'role': 'system', 'content': system_message},
                {'role': 'user', 'content': str(news)}
            ]
        }
    )
    completion.raise_for_status()

    response_data = completion.json()
    content = response_data['choices'][0]['message']['content']
    analysis = NewsAnalysis.parse_raw(content)

    return analysis

async def update_news() :
    print("업데이트 됨")
    with Session(engine) as session:  # 직접 세션 생성
        while True:
            try:
                analysis = get_completion()
                db.save_news_analysis(session, analysis)
                break
            except Exception as e:
                print(e)
                continue


@app.on_event("startup")
async def startup():
    db.create_db_and_tables()
    await update_news()

    scheduler.add_job(
        update_news,
        IntervalTrigger(minutes=30),
        id="update_news",
        replace_existing=True
    )
    scheduler.add_job(
        keep_alive,
        IntervalTrigger(minutes=4),
        id="keep_alive",
        replace_existing=True
    )
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_scheduler():
    server_state.is_running = False
    scheduler.shutdown()

@app.get("/")
def root():
    server_state.last_activity = datetime.now() 
    return {"message": "server is running", "last_activity": server_state.last_activity.isoformat()}

@app.get("/news", response_model=NewsResponse)
@limiter.limit("5/minute")
def api(request: Request):
    server_state.last_activity = datetime.now()
    with Session(engine) as session:
        news = NewsSQLModelDB.get_news(session)
        return NewsResponse.from_orm(news)