"""Existing author snapshots resolve by identity without touching estimate content."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1]/'apps/backend/alembic/versions/0004_employee_author_names.py'
spec = importlib.util.spec_from_file_location('author_names_migration',path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EmployeeAuthorNames(unittest.TestCase):
    def test_pre_final_old_names_and_login_aliases_are_corrected(self):
        users = [{'id':'mary','name':'Mary Razumna','email':'mary.razumna'}, {'id':'kate','name':'Kate Lukovych','email':'kate.lukovych'}]
        history = [{'entity_id':'mary','changes':{'name':{'before':'Маша','after':'Mary Razumna'},'email':{'before':'masha','after':'mary.razumna'}}},
                   {'entity_id':'kate','changes':{'name':{'before':'Катя 2','after':'Kate Lukovych'}}}]
        estimates = [{'id':ident,'user_id':'mary','prepared_by':'Маша','created_by_name':'masha','updated_by_name':'Катя 2', 'final_total':100} for ident in ['pre','final']]
        changes = list(module.author_changes(users,history,estimates))
        self.assertEqual(len(changes),2)
        for _, fields in changes:
            self.assertEqual(fields['prepared_by']['after'],'Mary Razumna')
            self.assertEqual(fields['created_by_name']['after'],'Mary Razumna')
            self.assertEqual(fields['updated_by_name']['after'],'Kate Lukovych')
            self.assertEqual(set(fields),set(module.FIELDS))
        for estimate in estimates:
            for field,detail in dict(changes)[estimate['id']].items():estimate[field]=detail['after']
            self.assertEqual(estimate['final_total'],100)
        self.assertEqual(list(module.author_changes(users,history,estimates)),[])

    def test_ambiguous_editor_and_unknown_historical_names_are_preserved(self):
        users = [{'id':'a','name':'Person A','email':'a.login'},{'id':'b','name':'Person B','email':'b.login'}]
        history = [{'entity_id':ident,'changes':{'name':{'before':'Old name'}}} for ident in ['a','b']]
        estimates = [{'id':'e','user_id':'a','prepared_by':'Old name','created_by_name':'External preparer','updated_by_name':'Old name'}]
        changes = list(module.author_changes(users,history,estimates))[0][1]
        self.assertEqual(changes,{'prepared_by':{'before':'Old name','after':'Person A'}})
