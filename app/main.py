from fastapi import FastAPI
from app.modules.price_compare.route import router as price_compare_router

app = FastAPI()

app.include_router(price_compare_router)
