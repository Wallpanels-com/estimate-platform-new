"""Code-owned calculator rules. Catalogue categories never register executable rules.

A future automatic type must register a handler here, a validated request model
and endpoint in the API, and its corresponding input form in the frontend. No user-authored expressions
or arbitrary catalogue identifiers are executed as calculator names.
"""
from dataclasses import dataclass
from typing import Callable
from app.services.rule_engine import calc_wall, calc_cabinet, calc_mirror

@dataclass(frozen=True)
class CalculatorRule:
    id: str
    label: str
    unit: str
    version: int
    calculate: Callable

RULES={rule.id:rule for rule in [
    CalculatorRule('wall','Wall panels','SF',1,calc_wall),
    CalculatorRule('cabinet','Cabinetry','LF',1,calc_cabinet),
    CalculatorRule('mirror','Mirror','SF',1,calc_mirror),
]}

def calculate(identifier,config,**validated_parameters):
    from copy import deepcopy
    from fastapi import HTTPException
    label=None
    if identifier=='mirror':
        key=validated_parameters.pop('mirror_type',None)
        if key:
            entry=config['mirror'].get('types',{}).get(key)
            if not entry:raise HTTPException(422,'Choose an existing mirror type.')
            config=deepcopy(config);config['mirror']['rate']=entry['rate'];label=entry['label']
    if identifier=='wall':
        key=validated_parameters.pop('base_rate_key',None)
        if key:
            if key not in config['wall']['base_rates']:raise HTTPException(422,'Choose an existing base rate.')
            from app.services.rule_engine import wall_size_tier
            from decimal import Decimal
            config=deepcopy(config)
            config['wall']['base_rates'][wall_size_tier(Decimal(str(validated_parameters.get('square_footage') or 0)))]=config['wall']['base_rates'][key]
    result = RULES[identifier].calculate(config=config,**validated_parameters)
    if label and result['line_items']:result['line_items'][0]['name']=label
    if identifier == 'mirror' and result['line_items']:
        # Keep the original formula/total, but persist installation separately so
        # an ordinary quantity edit cannot discard the fixed installation fee.
        from decimal import Decimal
        item = dict(result['line_items'][0])
        material = Decimal(str(item['quantity'])) * Decimal(str(item['unit_price']))
        installation = Decimal(str(item['total_price'])) - material
        item['total_price'] = float(material)
        result = {**result, 'line_items': [item]}
        if installation:
            result['line_items'].append({
                'section': 'Mirrors', 'name': 'Mirror Delivery & Installation',
                'description': '', 'calc_type': 'fixed', 'quantity': 1,
                'unit': 'ea', 'unit_price': float(installation),
                'total_price': float(installation),
            })
    return result

def definitions():
    return [{'id':r.id,'label':r.label,'unit':r.unit,'version':r.version} for r in RULES.values()]
