"""后端启动脚本: python run.py  (等价 uvicorn app.main:app --reload)。"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
