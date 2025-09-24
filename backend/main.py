# backend/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# [关键修复] 再次确认已移除所有手动修改 sys.path 的代码。
# 这是保证在标准化容器环境中稳定启动的第一步。

# --- 静态导入所有功能模块的路由 ---
from features.core_api.router import router as core_api_router
from features.chess_academy.router import router as chess_academy_router
# ==============================================================================
# [示例] 如何添加新的功能模块
# ------------------------------------------------------------------------------
# 当您在 backend/features/ 目录下创建一个新功能 (例如 my_new_feature) 后,
# 您需要在这里导入它的 router。
#
# from features.my_new_feature.router import router as my_new_feature_router
# ==============================================================================
#
# --- [已移除功能的示例] ---
# from features.bank_statement_analyzer.router import router as bank_statement_analyzer_router
# from features.second_hand_valuer.router import router as second_hand_valuer_router
# from features.english_writing_practice.router import router as english_writing_practice_router
# from features.kidtype_english.router import router as kidtype_english_router


app = FastAPI(
    title="flashmvp Backend API (Modular)",
    description="A modular API for the flashmvp project, running on Google Cloud Run.",
    version="2.4.0" # Bump version for new feature
)

# --- CORS 中间件配置 ---
origins = [
    "http://localhost:8787",
]
if os.getenv("ALLOWED_ORIGINS"):
    additional_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS").split(",")]
    origins.extend(additional_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# --- 注册所有已导入的路由 ---
# [FIX] The "/api" prefix is now applied here, consistently for all routers.
# This centralizes routing logic and prevents conflicts.
app.include_router(core_api_router, prefix="/api")
print("✅ Successfully loaded feature: core_api")
app.include_router(chess_academy_router, prefix="/api")
print("✅ Successfully loaded feature: chess_academy")

# ==============================================================================
# [示例] 如何注册新的功能模块路由
# ------------------------------------------------------------------------------
# 导入 router 后, 您需要在这里使用 app.include_router() 将其注册到 FastAPI 应用中。
#
# app.include_router(my_new_feature_router, prefix="/api")
# print("✅ Successfully loaded feature: my_new_feature")
# ==============================================================================
#
# --- [已移除功能的示例] ---
# The 'bank_statement_analyzer' is now enabled.
# app.include_router(bank_statement_analyzer_router, prefix="/api")
# print("✅ Successfully loaded feature: bank_statement_analyzer")
#
# Register the new Second-hand Valuer feature
# app.include_router(second_hand_valuer_router, prefix="/api")
# print("✅ Successfully loaded feature: second_hand_valuer")
#
# app.include_router(english_writing_practice_router, prefix="/api")
# print("✅ Successfully loaded feature: english_writing_practice")
#
# app.include_router(kidtype_english_router, prefix="/api")
# print("✅ Successfully loaded feature: kidtype_english")


# --- 平台级端点 ---
@app.get("/", include_in_schema=False)
def read_root():
    return {"message": "Welcome to the flashmvp Modular Backend API. See /docs for documentation."}
