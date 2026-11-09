import sys, unittest
from pathlib import Path
from io import BytesIO
from openpyxl import Workbook
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/backend'))
from app.services.hr_import import parse_workbook, suggest_mapping, prepare_rows, contact_flags, suggested_questions, row_keys
from app.services.hr_scoring import qualification_score

class HRImportTests(unittest.TestCase):
    def workbook(self,rows):
        w=Workbook();s=w.active
        for row in rows:s.append(row)
        b=BytesIO();w.save(b);return b.getvalue()
    def test_mapping_ignores_facebook_ad_name_and_preserves_original_answers(self):
        data=parse_workbook(self.workbook([['ad_name','полное_имя','эл._адрес','оставьте_ваш_контактный_номер_телефона','Experience'],['Ad','Example','A@example.com','+1234567890','3 years'],[None]*5]))
        s=data['sheets'][0];m=suggest_mapping(s['columns']);self.assertEqual(m['name'],'полное_имя')
        rows,info=prepare_rows(s['rows'],m);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['answers']['Experience'],'3 years');self.assertEqual(rows[0]['email'],'a@example.com')
    def test_test_leads_incomplete_rows_and_invalid_workbooks(self):
        rows,info=prepare_rows([{'name':'','email':'a@x.com'},{'name':'<test lead: dummy data>','email':'b@x.com'},{'name':'Example','email':'c@x.com'}],{'name':'name','email':'email','phone':''})
        self.assertEqual(info,{'invalid':1,'test_rows':1});self.assertEqual(len(rows),1)
        with self.assertRaises(ValueError):parse_workbook(b'not an xlsx')
        duplicate=parse_workbook(self.workbook([['Name','Name'],['a','b']]))['sheets'][0]
        self.assertEqual(duplicate['columns'],['Name','Name (2)'])
        self.assertEqual(duplicate['rows'][0],{'Name':'a','Name (2)':'b'})
    def test_contact_flags_are_neutral_and_never_affect_score(self):
        self.assertEqual(contact_flags('+7 (123) 456-78-90','person@EXAMPLE.RU'),['phone_plus7','email_ru'])
        self.assertEqual(contact_flags('+380123456789','example.ru@gmail.com'),[])
        answers={'сколько_лет_вы_работаете_в_маркетинге?':'более_8_лет','какой_у_вас_уровень_английского?':'c1–c2_(продвинутый)','есть_ли_у_вас_опыт_работы_с_американским_рынком?':'более_3_лет'}
        self.assertEqual(qualification_score(answers)['score'],100)
        self.assertEqual(qualification_score(answers|{'email':'someone@x.ru','phone':'+7','Priority':'low','country':'Russia','age':'80','sex':'female'}),qualification_score(answers))
        self.assertIsNone(qualification_score({'name':'Example'})['score'])
    def test_professional_ranking_and_missing_criteria(self):
        result=qualification_score({'насколько_хорошо_вы_читаете_технические_чертежи?':'есть_базовый_опыт','сколько_лет_опыта_у_вас_в_управлении_проектами?':'3–5_лет'})
        self.assertEqual(result['score'],64);self.assertEqual(len(result['evidence']),2)

    def test_multilingual_meta_contacts_and_selected_answers(self):
        columns=['ad_name','first_name','last_name','phone_number','email','lead_status','досвід_конструювання?','програми?']
        data=parse_workbook(self.workbook([columns,['Ad','Example','Person','p:+380 67 111 22 33','e:EXAMPLE@MAIL.COM','new','5 years','CAD']]))['sheets'][0]
        mapping=suggest_mapping(data['columns'],data['rows'])
        self.assertEqual(mapping['name'],'first_name');self.assertEqual(mapping['last_name'],'last_name')
        self.assertEqual(mapping['phone'],'phone_number')
        questions=suggested_questions(data['columns'],mapping,data['rows'])
        self.assertEqual(questions,['досвід_конструювання?','програми?'])
        people,_=prepare_rows(data['rows'],mapping,['програми?']);p=people[0]
        self.assertEqual((p['name'],p['email'],p['phone']),('Example Person','example@mail.com','+380 67 111 22 33'))
        self.assertEqual(p['answers'],{'програми?':'CAD'})
        self.assertTrue(row_keys(p)&row_keys({'email':'EXAMPLE@MAIL.COM','phone':''}))
        self.assertTrue(row_keys(p)&row_keys({'email':'','phone':'00380671112233'}))
        self.assertEqual(suggest_mapping(['ad_name','ім’я','номер_телефону','електронна_пошта'])['name'],'ім’я')

    def test_title_rows_blank_columns_and_numeric_phones(self):
        result=parse_workbook(self.workbook([['Candidate export'],[],['Name','email','Phone',None,None],['Example','person@example.com',380671112233,None,None]]))['sheets'][0]
        self.assertEqual(result['header_row'],3)
        self.assertEqual(result['columns'],['Name','email','Phone'])
        self.assertEqual(result['rows'][0]['Phone'],'380671112233')
        self.assertEqual(suggest_mapping(['ad_name','campaign_id','Contact'],[{'ad_name':'Ad','campaign_id':'123456789','Contact':'person@example.com'}])['email'],'Contact')

    def test_full_name_does_not_append_surname_twice(self):
        mapping=suggest_mapping(['full_name','last_name','email'])
        people,_=prepare_rows([{'full_name':'Example Person','last_name':'Person','email':'person@example.com'}],mapping,[])
        self.assertEqual(people[0]['name'],'Example Person')
        self.assertEqual(suggest_mapping(['повне_ім’я','email'])['name'],'повне_ім’я')

    def test_telegram_only_and_empty_question_selection(self):
        rows,info=prepare_rows([{'Name':'Example','Telegram':'@example_user','Notes':'Other'}],{'name':'Name','email':'','phone':'','telegram':'Telegram'},[])
        self.assertEqual(info,{'invalid':0,'test_rows':0})
        self.assertEqual(rows[0]['telegram_username'],'example_user');self.assertEqual(rows[0]['answers'],{})
        self.assertFalse(prepare_rows([{'Name':'Example','Telegram':'bad url'}],{'name':'Name','email':'','phone':'','telegram':'Telegram'})[0])
