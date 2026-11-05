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
    # Give older generated messages the same section hierarchy as new ones.
    if not any(re.search(r'(?m)^(?:Про компанію|Про вакансію|Наступний крок)\s*$',p) for p in paragraphs):
        role=[];conditions=[];next_step=[]
        for part in paragraphs:
            if re.match(r'^(?:Вітаю|Мене звати|Я Вікторія|Дяку|Ваша заявка|Ваш відгук)',part,re.I):continue
            if re.match(r'^(?:Wallpanels|Ми\s*[—–-]|Наша компанія|Ми компанія)',part,re.I):continue
            if re.match(r'^(?:Будь ласка|Надішліть|Буду рада|Чекаємо|Просимо)',part,re.I):next_step.append(part)
            elif re.match(r'^(?:Робота|Графік|Умови|Формат роботи)',part,re.I):conditions.append(part)
            else:role.append(part)
        paragraphs=['Вітаю!','Мене звати Вікторія, я рекрутер Wallpanels.com.',f'Дякую за відгук на вакансію «{vacancy_name}».',
            'Про компанію\nWallpanels.com створює інтер’єрні стінові панелі та дизайнерські рішення для житлових і комерційних просторів у США.',
            'Про вакансію\n'+('\n\n'.join(role) if role else 'Буду рада розповісти детальніше про завдання під час короткої розмови.')]
        if conditions:paragraphs.append('Умови\n'+'\n\n'.join(conditions))
        paragraphs.append('Наступний крок\n'+('\n\n'.join(next_step) if next_step else 'Будь ласка, надішліть ваше актуальне резюме або портфоліо та повідомте про вашу доступність для короткої розмови.'))
    return '\n\n'.join(paragraphs)+'\n\nСайт: '+LINKS[0]+'\nInstagram: '+LINKS[1]
