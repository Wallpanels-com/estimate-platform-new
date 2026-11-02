"""Explicit, equally weighted professional criteria requested by the hiring team.
Self-reported answers support human review; no demographic/contact/source-priority input.
"""
import re

def normalized(s):
    return re.sub(r'\s+', ' ', str(s).lower().replace('_',' ').replace('–','-').replace('—','-')).strip()

def qualification_score(answers):
    evidence=[]; used=set()
    for question,answer in answers.items():
        q=normalized(question);a=normalized(answer);key=None;points=0
        if ('сколько лет' in q and ('опыта' in q or 'маркетинг' in q)) or 'years of experience' in q:
            key='experience'
            points=25 if any(x in a for x in ['более 8','более 5','5-8','8+','5+']) else 20 if '3-5' in a else 12 if any(x in a for x in ['1-3','1-2']) else 0
        elif 'английского' in q or 'english level' in q:
            key='english'
            points=25 if any(x in a for x in ['c1','c2','свободное владение','fluent']) else 20 if 'b2+' in a or 'b2 (' in a or 'b2 выше' in a else 12 if 'b1' in a else 0
        elif ('американским рынком' in q) or 'us market' in q:
            key='us_market'
            points=25 if any(x in a for x in ['более 3','3+']) else 20 if '1-3' in a else 10 if 'менее 1' in a else 0
        elif 'чертеж' in q or 'technical drawing' in q:
            key='drawings'
            points=25 if 'хорошо читаю' in a or a in ('advanced','proficient') else 12 if 'базов' in a or a=='basic' else 0
        if key and key not in used:
            used.add(key);evidence.append({'criterion':key,'question':question,'answer':answer,'points':points,'maximum':25})
    return {'score':round(sum(e['points'] for e in evidence)*100/(25*len(evidence))) if evidence else None,'evidence':evidence}
