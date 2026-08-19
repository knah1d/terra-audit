from fastapi import APIRouter, Depends

from backend.deps import get_current_user
from src.database import get_portfolio_summary

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio/summary")
def portfolio_summary(user: dict = Depends(get_current_user)):
    return get_portfolio_summary(user["org_id"])
