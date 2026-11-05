"""Recruiter-facing message presentation, independent of the account author."""
import re

RECRUITER_NAME = 'Вікторія'
LINKS = ('https://wallpanels.com', 'https://www.instagram.com/wallpanels_com')

def format_outreach(message: str, vacancy_name: str, author_name: str = '') -> str:
    text=message.replace('{{recruiter_name}}',RECRUITER_NAME).replace('{{vacancy_name}}',vacancy_name).strip()
    # Old generated messages contain the account name. Correct only the introduction;
    # the actual author metadata and any unrelated mention of a colleague stay intact.
    text=re.sub(r'(Мене\s+звати\s+)[A-ZА-ЯІЇЄҐ][\w’\'-]*(?:[ \t]+[A-ZА-ЯІЇЄҐ][\w’\'-]*){0,2}',lambda m:m.group(1)+RECRUITER_NAME,text)
    if author_name:
        text=re.sub(r'(\bЯ\s+)'+re.escape(author_name)+r'(?=[,\s.!?])',lambda m:m.group(1)+RECRUITER_NAME,text,flags=re.I)
    if not re.search(r'(?:Мене\s+звати|\bЯ)\s+Вікторія',text,re.I):
        text='Вітаю!\nМене звати Вікторія, я рекрутер Wallpanels.com.\n\n'+re.sub(r'^Вітаю!\s*','',text)
    text=text.replace('ваш актуальний резюме','ваше актуальне резюме').replace('ваш актуальне резюме','ваше актуальне резюме')
    # Keep links on separate lines, with a single consistent footer.
    for link in sorted(LINKS,key=len,reverse=True):
        text=re.sub(re.escape(link)+r'/?[.,;]?', '',text)
    paragraphs=[]
    for paragraph in re.split(r'\n\s*\n',text):
        paragraph=paragraph.strip()
        if not paragraph:continue
        # Older one-block responses become short, readable paragraphs immediately,
        # without another model request or overwriting saved records.
        for sentence in re.split(r'(?<=[.!?])\s+(?=[А-ЯІЇЄҐA-Z«])',paragraph):
            sentence=sentence.strip()
            sentence=re.sub(r'(?im)^\s*(?:Сайт|Instagram|Інстаграм|Наш сайт та інстаграм|Більше про нас|Детальніше про нас|Додаткова інформація про компанію доступна на)\s*[:—–-]?\s*[,;]?\s*$', '',sentence).strip()
            if sentence and sentence not in (',',';','та','і'):
                paragraphs.append(sentence)
    return '\n\n'.join(paragraphs)+'\n\nСайт: '+LINKS[0]+'\nInstagram: '+LINKS[1]
