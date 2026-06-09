from fastapi import APIRouter, Form
from .controller import fetch_price_compare

router = APIRouter(prefix="/price")

@router.post("/compare")
async def price_compare(search_term: str = Form(...)):
    return await fetch_price_compare(search_term)
