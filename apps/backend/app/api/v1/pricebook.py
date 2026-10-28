from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.pricebook import CategoryInput, ItemInput, QuoteInput
from app.services.pricing_config import get_pricing_config
from app.services.pricebook_service import categories, read_catalog, update_category, update_item, quote, delete_entry

router=APIRouter(prefix='/pricing/catalog',tags=['price-book'])

def display(user):return user.name or user.email

@router.get('')
async def get_catalog(db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user)):
    config=await get_pricing_config(db)
    return {'categories':categories(config),'items':read_catalog(config)['items']}

@router.post('/categories',status_code=201)
async def create_category(data:CategoryInput,db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user)):
    return await update_category(db,data,display(user))

@router.put('/categories/{ident}')
async def edit_category(ident:str,data:CategoryInput,db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user)):
    return await update_category(db,data,display(user),ident)

@router.post('/items',status_code=201)
async def create_item(data:ItemInput,db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user)):
    return await update_item(db,data,display(user))

@router.put('/items/{ident}')
async def edit_item(ident:str,data:ItemInput,db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user)):
    return await update_item(db,data,display(user),ident)

@router.post('/items/{ident}/quote')
async def quote_item(ident:str,data:QuoteInput,db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user)):
    return quote(await get_pricing_config(db),ident,data.quantity)

@router.delete('/categories/{ident}',status_code=204)
async def delete_category(ident:str,expected_version:int=Query(ge=0),db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user)):
    await delete_entry(db,'categories',ident,expected_version,display(user))

@router.delete('/items/{ident}',status_code=204)
async def delete_item(ident:str,expected_version:int=Query(ge=1),db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user)):
    await delete_entry(db,'items',ident,expected_version,display(user))
