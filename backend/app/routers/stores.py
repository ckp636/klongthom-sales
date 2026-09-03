from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories import store_repo
from app.schemas.log import LogCreate
from app.schemas.store import StoreCreate, StoreOut, StoreUpdate
from app.services import log_service

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("/", response_model=list[StoreOut])
async def list_stores(db: AsyncSession = Depends(get_db)):
    return await store_repo.get_all(db)


@router.get("/{sid}", response_model=StoreOut)
async def get_store(sid: int, db: AsyncSession = Depends(get_db)):
    store = await store_repo.get_by_id(db, sid)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return store


@router.post("/", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
async def create_store(data: StoreCreate, db: AsyncSession = Depends(get_db)):
    existing = await store_repo.get_by_code(db, data.s7Code)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Store code already exists")
    store = await store_repo.create(db, data)
    await log_service.write(db, LogCreate(
        l9Type="audit", l9Module="store", l9Action="create",
        l9Page="/stores", l9Component="create_store",
        l9Sid=store.s7Sid, l9NewVal=store.s7Code,
    ))
    return store


@router.patch("/{sid}", response_model=StoreOut)
async def update_store(sid: int, data: StoreUpdate, db: AsyncSession = Depends(get_db)):
    store = await store_repo.get_by_id(db, sid)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    store = await store_repo.update(db, store, data)
    await log_service.write(db, LogCreate(
        l9Type="audit", l9Module="store", l9Action="update",
        l9Page="/stores", l9Component="update_store",
        l9Sid=store.s7Sid, l9RefID=store.s7Sid, l9RefTable="mod7$_Store",
    ))
    return store
