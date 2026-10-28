"""Managed catalogue stored alongside (never interpreted as) legacy pricing rules."""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import hashlib, json, math, uuid
from fastapi import HTTPException
from sqlalchemy import text
from app.services.pricing_config import DEFAULT_PRICING_CONFIG, get_pricing_config, save_pricing_config

CATALOG_KEY = '_catalog_v1'
BUILTINS = [
    ('wall','Wall panels','panels'),('cabinet','Cabinetry','cabinet'),('mirror','Mirrors','mirror'),
    ('materials','Materials','materials'),('quick_estimate','Quick estimate','quick'),
    ('services','Services','services'),('colors','Colors & finishes','colors'),
]
CALCULATORS = {'wall','cabinet','mirror'}

def legacy_config(config):
    return {k:deepcopy(v) for k,v in config.items() if k != CATALOG_KEY}

def revision(config):
    return hashlib.sha256(json.dumps(legacy_config(config),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def read_catalog(config):
    return deepcopy(config.get(CATALOG_KEY) or {'categories':[], 'items':[], 'overrides':{}})

def categories(config):
    book=read_catalog(config)
    defaults=[{'id':key,'name':name,'name_ru':'','description':'','description_ru':'','icon':icon,'archived':False,'version':0,**book['overrides'].get(key,{}),'builtin':True,'calculator_id':key if key in CALCULATORS else None} for key,name,icon in BUILTINS]
    return [{'parent_id':None,**c} for c in defaults + [{**c,'builtin':False,'calculator_id':None} for c in book['categories']]]

def category_available(config, ident):
    """Archiving a parent hides its descendants without destroying their state."""
    seen=set()
    while ident:
        if ident in seen:return False
        seen.add(ident)
        entry=category(config,ident)
        if entry['archived']:return False
        ident=entry.get('parent_id')
    return True

def category(config, ident):
    result=next((c for c in categories(config) if c['id']==ident),None)
    if result is None:raise HTTPException(404,'Category not found.')
    return result

def version_check(entity, expected):
    if expected is not None and entity['version'] != expected:
        raise HTTPException(409,'This entry changed elsewhere. Reload it before saving.')

def category_change(config, payload, ident=None):
    result=deepcopy(config);book=read_catalog(config)
    old=category(config,ident) if ident else None
    data=payload.model_dump(exclude={'expected_version'})
    if data.get("parent_id"):
        raise HTTPException(422,"Subcategories are not supported. Choose a top-level category.")
    if old:
        version_check(old,payload.expected_version)
        if old['builtin'] and data['archived']:raise HTTPException(409,'Built-in categories cannot be archived.')
        if old['builtin'] and data['parent_id']:raise HTTPException(409,'Built-in categories must stay at the top level.')
    elif data['archived']:raise HTTPException(422,'Create an active category first.')
    parent=data['parent_id'];seen={ident} if ident else set()
    while parent:
        if parent in seen:raise HTTPException(422,'A category cannot be placed inside itself or its descendants.')
        seen.add(parent)
        parent_entry=category(config,parent)
        if parent_entry['archived'] and not data['archived']:raise HTTPException(409,'Restore the parent category first.')
        parent=parent_entry.get('parent_id')
    if any(c['id'] != ident and c.get('parent_id')==data['parent_id'] and c['name'].casefold()==data['name'].casefold() for c in categories(config)):
        raise HTTPException(409,'A category with this name already exists.')
    entry={**data,'id':ident or str(uuid.uuid4()),'version':old['version']+1 if old else 1}
    if old and old['builtin']:book['overrides'][ident]=entry
    elif old:book['categories']=[entry if c['id']==ident else c for c in book['categories']]
    else:book['categories'].append(entry)
    result[CATALOG_KEY]=book
    return result,entry['id']

def item_change(config,payload,ident=None):
    result=deepcopy(config);book=read_catalog(config)
    old=next((item for item in book['items'] if item['id']==ident),None)
    if ident and not old:raise HTTPException(404,'Price Book item not found.')
    if old:version_check(old,payload.expected_version)
    cat=category(config,payload.category_id)
    if not category_available(config,cat['id']) and not payload.archived:raise HTTPException(409,'Restore this category before editing active items.')
    data=payload.model_dump(mode='json',exclude={'expected_version'})
    entry={**data,'id':ident or str(uuid.uuid4()),'version':old['version']+1 if old else 1}
    if old:book['items']=[entry if item['id']==ident else item for item in book['items']]
    else:book['items'].append(entry)
    result[CATALOG_KEY]=book
    return result,entry

def quote(config,ident,quantity):
    item=next((item for item in read_catalog(config)['items'] if item['id']==ident),None)
    if not item:raise HTTPException(404,'Price Book item not found.')
    cat=category(config,item['category_id'])
    if item['archived'] or not category_available(config,cat['id']):raise HTTPException(409,'This Price Book item is archived.')
    qty=Decimal('1') if item['pricing_mode']=='fixed' else quantity
    rate=Decimal(str(item['unit_price'])) if item['unit_price'] is not None else None
    total=((rate or Decimal('0'))*qty).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    if total>Decimal('9999999999.99'):raise HTTPException(422,'The item total is too large.')
    detail='\n'.join([item['description']]+[f"{p['name']}: {p['value']}" for p in item['parameters']]).strip()
    return {'section':cat['name'],'name':item['name'],'description':detail,'calc_type':'sf' if item['unit']=='SF' else 'lf' if item['unit']=='LF' else 'fixed','quantity':str(qty),'unit':item['unit'],'unit_price':str(rate) if rate is not None else None,'total_price':str(total),'is_tbd':item['pricing_mode']=='unpriced'}

async def lock_config(db):
    # Serializes catalogue and legacy writes, including first creation of the singleton.
    await db.execute(text('SELECT pg_advisory_xact_lock(782431650)'))

async def update_category(db,payload,user,ident=None):
    await lock_config(db)
    config=await get_pricing_config(db)
    updated,key=category_change(config,payload,ident)
    await save_pricing_config(db,updated,user)
    return category(updated,key)

async def update_item(db,payload,user,ident=None):
    await lock_config(db)
    config=await get_pricing_config(db)
    updated,item=item_change(config,payload,ident)
    await save_pricing_config(db,updated,user)
    return item

def validate_legacy(config):
    def walk(value,default,path):
        if isinstance(default,dict):
            if not isinstance(value,dict) or any(k not in value for k in default):raise HTTPException(422,'Required pricing parameters cannot be removed.')
            for k,d in default.items():walk(value[k],d,path+[k])
        elif isinstance(default,list):
            if not isinstance(value,list):raise HTTPException(422,'Invalid pricing parameter type.')
        elif isinstance(default,bool):
            if not isinstance(value,bool):raise HTTPException(422,'Invalid pricing parameter type.')
        elif isinstance(default,(int,float)):
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:raise HTTPException(422,'Rates must be finite, non-negative numbers.')
        elif isinstance(default,str) and (not isinstance(value,str) or not value.strip()):raise HTTPException(422,'Pricing labels cannot be empty.')
    walk(config,DEFAULT_PRICING_CONFIG,[])
    for material in config.get('materials',{}).values():
        key=material.get('addon_key')
        if key is not None and key not in config['wall']['addons_sf']:raise HTTPException(422,'Select an existing wall upgrade for this material.')

async def save_legacy(db, incoming, user, expected=None, reset=False):
    await lock_config(db)
    current=await get_pricing_config(db)
    if expected is not None and revision(current)!=expected:raise HTTPException(409,'Pricing changed elsewhere. Reload before saving your rates.')
    from app.services.managed_rates import with_managed_rates, validate_additions
    config=with_managed_rates(DEFAULT_PRICING_CONFIG) if reset else legacy_config(incoming)
    validate_additions(config)
    validate_legacy(config)
    if CATALOG_KEY in current:config[CATALOG_KEY]=deepcopy(current[CATALOG_KEY])
    row=await save_pricing_config(db,config,user)
    return {'config':row.config,'is_default':legacy_config(row.config)==with_managed_rates(DEFAULT_PRICING_CONFIG),'revision':revision(row.config),'updated_by':row.updated_by_name,'updated_at':row.updated_at}


def remove_entry(config, kind, ident, expected):
    result=deepcopy(config);book=read_catalog(config)
    if kind=='items':
        entry=next((i for i in book['items'] if i['id']==ident),None)
        if entry is None:raise HTTPException(404,'Price Book item not found.')
        version_check(entry,expected)
        if not entry['archived'] and category_available(config,entry['category_id']):raise HTTPException(409,'Archive the item before permanently deleting it.')
        book['items']=[i for i in book['items'] if i['id']!=ident]
    else:
        entry=category(config,ident);version_check(entry,expected)
        if entry['builtin']:raise HTTPException(409,'Built-in categories cannot be deleted.')
        if category_available(config,ident):raise HTTPException(409,'Archive the category before permanently deleting it.')
        deleted={ident}
        while True:
            following=deleted|{c['id'] for c in book['categories'] if c.get('parent_id') in deleted}
            if following==deleted:break
            deleted=following
        book['categories']=[c for c in book['categories'] if c['id'] not in deleted]
        book['items']=[i for i in book['items'] if i['category_id'] not in deleted]
    result[CATALOG_KEY]=book
    return result

async def delete_entry(db,kind,ident,expected,user):
    await lock_config(db)
    config=await get_pricing_config(db)
    await save_pricing_config(db,remove_entry(config,kind,ident,expected),user)
