import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/backend'))
from app.services.hr_outreach import format_outreach
from app.api.v1.hr_ai import output
from app.services.hr_ai import fingerprint
class OutreachTests(unittest.TestCase):
 def test_old_message_sender_paragraphs_and_links(self):
  raw='Вітаю! Мене звати Dmitry, я рекрутер Wallpanels.com. Дякую за відгук на вакансію Project Manager. Робота віддалена, вечірній графік. Будь ласка, надішліть резюме. Детальніше про нас: https://wallpanels.com, https://www.instagram.com/wallpanels_com'
  result=format_outreach(raw,'Project Manager','Dmitry')
  self.assertIn('Мене звати Вікторія',result);self.assertNotIn('Dmitry',result)
  self.assertIn('\n\nРобота віддалена',result)
  self.assertIn('Сайт: https://wallpanels.com\nInstagram:',result)
  self.assertEqual(result.count('https://wallpanels.com'),1)
  self.assertEqual(result,format_outreach(result,'Project Manager','Dmitry'))
 def test_intro_keeps_role_when_name_is_followed_by_conjunction(self):
  text=format_outreach('Вітаю! Мене звати Dmitry і я рекрутер Wallpanels.com. Надішліть резюме.','PM','Dmitry')
  self.assertIn('Вікторія і я рекрутер Wallpanels.com',text)
 def test_new_template_is_not_account_dependent(self):
  result=format_outreach('Вітаю! Мене звати {{recruiter_name}}, я рекрутер.\n\nПро вакансію\n{{vacancy_name}}.\n\nНаступний крок\nНадішліть резюме.','Marketer')
  self.assertIn('Вікторія',result);self.assertIn('Про вакансію\nMarketer',result)
 def test_read_updates_generated_message_but_preserves_manual_draft(self):
  source={'vacancy':'PM','requirements':'','answers':{}}
  original='Вітаю! Мене звати Dmitry, я рекрутер. Надішліть резюме.'
  r=SimpleNamespace(content={'message_uk':original,'summary':'Existing analysis'},message_draft=original,created_by='Dmitry',model='model',created_at=None,updated_at=None,source_hash=fingerprint(source))
  result=output(r,source)
  self.assertIn('Вікторія',result['message_draft']);self.assertEqual(result['created_by'],'Dmitry')
  self.assertEqual(r.message_draft,original);self.assertEqual(r.content['message_uk'],original)
  r.message_draft='Manually edited text'
  self.assertEqual(output(r,source)['message_draft'],'Manually edited text')
if __name__=='__main__':unittest.main()
