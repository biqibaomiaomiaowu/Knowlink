from server.api.app_factory import create_app

app = create_app()

# 添加启动代码
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # 热重载，代码改了自动重启
    )
