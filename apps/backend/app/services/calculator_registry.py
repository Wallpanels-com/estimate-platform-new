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
    return RULES[identifier].calculate(config=config,**validated_parameters)

def definitions():
    return [{'id':r.id,'label':r.label,'unit':r.unit,'version':r.version} for r in RULES.values()]
