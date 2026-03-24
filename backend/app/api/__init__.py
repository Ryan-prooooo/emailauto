from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import init_db, logger
from app.api.routes_agents import init_agents
from app.api.routes_agents import router as agents_router
from app.api.routes_chat import router as chat_router
from app.api.routes_core import router as core_router
from app.scheduler import scheduler


app = FastAPI(
    title="QQ邮箱智能生活事件助手",
    description="智能分析QQ邮箱中的邮件，提取重要事件并推送通知",
    version="1.0.0",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有 HTTP 请求"""
    logger.info(f"<<< REQUEST: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f">>> RESPONSE: {request.method} {request.url.path} -> {response.status_code}")
    return response


# 初始化数据库
@app.on_event("startup")
async def startup_event():
    logger.info("=== 应用启动 ===")
    init_db()
    from app.db.migrate import run_migrations
    run_migrations()
    scheduler.start()
    init_agents()
    logger.info("启动完成，已注册路由:")
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            logger.info(f"  - {list(route.methods)} {route.path}")
        elif hasattr(route, 'path'):
            logger.info(f"  - {route.path}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=== 应用关闭 ===")
    scheduler.stop()


# 前端静态目录（项目根目录下的 frontend）
# __file__ -> app/api/__init__.py -> parent*3 -> backend -> parent*4 -> 项目根
_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend"


# 根路由：跳转到前端页面
@app.get("/")
async def root():
    if _FRONTEND_DIR.exists() and (_FRONTEND_DIR / "index.html").exists():
        return FileResponse(_FRONTEND_DIR / "index.html")
    return {"message": "QQ邮箱智能生活事件助手 API", "version": "1.0.0"}


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# 托管前端静态资源（仅当 frontend 目录存在时）
if _FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")


# 挂载 /api 路由（统一前缀，与前端 baseURL 一致）
app.include_router(core_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(agents_router, prefix="/api")

logger.info("已挂载所有 API 路由（/api）")
