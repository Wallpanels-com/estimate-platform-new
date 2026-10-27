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
    result = RULES[identifier].calculate(config=config,**validated_parameters)
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
