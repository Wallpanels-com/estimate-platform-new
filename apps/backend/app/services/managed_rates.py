"""Supported additions to existing formulas; never user-authored expressions."""
from copy import deepcopy
from fastapi import HTTPException
from app.services.rule_engine import get_pricing_schema

MIRRORS = {
    'rustic': {'label':'Rustic Mirror','label_ru':'Деревенское зеркало','rate':100},
    'bronze': {'label':'Bronze Mirror','label_ru':'Бронзовое зеркало','rate':100},
    'clear': {'label':'Clear Mirror','label_ru':'Чистое зеркало','rate':80},
}

def with_managed_rates(config):
    result=deepcopy(config)
    types=result.setdefault('mirror',{}).setdefault('types',{})
    for key,value in MIRRORS.items():types.setdefault(key,deepcopy(value))
    result.setdefault('cabinet',{}).setdefault('types',{}).setdefault('shelving_unit',{'label':'Shelving Unit','label_ru':'Полочный шкаф','base_rate':800})
    return result


def pricing_schema(config):
    result=get_pricing_schema(config)
    result['mirror']['types']=[{'key':key,'label':v['label'],'label_ru':v.get('label_ru',''),'rate':v['rate']} for key,v in config['mirror'].get('types',{}).items()]
    for cat,groups in {'wall':['base_rates','addons_sf','addons_fixed'],'cabinet':['types','addons_lf','glass_doors']}.items():
        for group in groups:
            for entry in result[cat].get(group,[]):
                source=config[cat].get(group,{}).get(entry['key'])
                if isinstance(source,dict):entry['label_ru']=source.get('label_ru','')
                label=config.get('_rate_labels',{}).get('.'.join([cat,group,entry['key']]))
                if label:entry.update(label)
    return result


def validate_additions(config):
    """Validate extra entries too; the legacy validator only walks original keys."""
    import math
    def number(value):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or value>9999999999.99:
            raise HTTPException(422,'Rates must be finite, non-negative numbers.')
    def walk(value):
        if isinstance(value,(int,float)) and not isinstance(value,bool):number(value)
        elif isinstance(value,dict):
            for v in value.values():walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
    walk(config)
    for cat,group,amount in [('wall','addons_sf','price'),('wall','addons_fixed','price'),('cabinet','types','base_rate'),('cabinet','addons_lf','price'),('cabinet','glass_doors','price'),('mirror','types','rate'),('services',None,'default_price')]:
        entries=config.get(cat,{}) if group is None else config.get(cat,{}).get(group,{})
        if not isinstance(entries,dict):raise HTTPException(422,'Invalid rate group.')
        for entry in entries.values():
            if not isinstance(entry,dict) or not isinstance(entry.get('label'),str) or not entry['label'].strip():raise HTTPException(422,'A rate name is required.')
            number(entry.get(amount))
    for value in config['wall']['base_rates'].values():number(value)


async def get_config(db):
    from app.services.pricing_config import get_pricing_config
    return with_managed_rates(await get_pricing_config(db))
