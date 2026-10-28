"""Check flat categories, archive/delete and supported calculator rates using only newly created TEST entries."""
import argparse
import json
from pathlib import Path
import uuid
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', type=Path, required=True)
    parser.add_argument('--base', default='https://estimate-platform-production.up.railway.app/api/v1')
    args = parser.parse_args()
    users = json.loads(args.credentials.read_text())['users']
    clients = []
    checks = 0
    for user in users[:2]:
        client = httpx.Client(base_url=args.base, trust_env=False, timeout=60)
        login = client.post('/auth/login', json={'email': user['login'], 'password': user['password']})
        login.raise_for_status()
        client.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
        clients.append(client)
    a, b = clients
    created_categories = set()
    created_items = set()
    def call(client, method, path, status=200, **kwargs):
        nonlocal checks
        response = client.request(method, path, **kwargs)
        assert response.status_code == status, f'{method} {path}: {response.status_code} {response.text[:180]}'
        checks += 1
        return response.json() if response.content else None
    def cat_body(entry, **updates):
        return {**{k: entry.get(k) for k in ['name','name_ru','description','description_ru','icon','archived','parent_id']},
                'expected_version': entry['version'], **updates}
    def item_body(entry, **updates):
        return {**{k:v for k,v in entry.items() if k not in {'id','version'}}, 'expected_version':entry['version'], **updates}
    prefix = 'TEST Price Book ' + uuid.uuid4().hex[:8]
    before = call(a, 'GET', '/pricing/config')['revision']
    try:
        parent = call(a,'POST','/pricing/catalog/categories',201,json={'name':prefix,'name_ru':'ТЕСТ редактирования справочника','icon':'folder'})
        created_categories.add(parent['id'])
        child = call(b,'POST','/pricing/catalog/categories',201,json={'name':prefix+' finishes','name_ru':'Акустическая отделка','icon':'panels'})
        created_categories.add(child['id'])
        grandchild = call(a,'POST','/pricing/catalog/categories',201,json={'name':prefix+' oak'})
        created_categories.add(grandchild['id'])
        call(b,'PUT',f"/pricing/catalog/categories/{parent['id']}",422,json=cat_body(parent,parent_id=grandchild['id']))
        renamed = call(b,'PUT',f"/pricing/catalog/categories/{child['id']}",json=cat_body(child,name=prefix+' wall finishes',name_ru='Акустические стеновые покрытия'))
        call(a,'PUT',f"/pricing/catalog/categories/{child['id']}",409,json=cat_body(child,name='Stale edit'))
        entry = call(b,'POST','/pricing/catalog/items',201,json={'category_id':grandchild['id'],'name':'TEST Acoustic panel','unit':'SF','unit_price':'12.50','default_quantity':'2'})
        created_items.add(entry['id'])
        q = call(a,'POST',f"/pricing/catalog/items/{entry['id']}/quote",json={'quantity':'4'})
        assert q['total_price'] == '50.00'
        edited = call(a,'PUT',f"/pricing/catalog/items/{entry['id']}",json=item_body(entry,unit_price='15.25',description='Shared edit check'))
        call(b,'PUT',f"/pricing/catalog/items/{entry['id']}",409,json=item_body(entry,unit_price='1'))
        q = call(b,'POST',f"/pricing/catalog/items/{entry['id']}/quote",json={'quantity':'4'})
        assert q['total_price'] == '61.00'
        fixed = call(a,'POST','/pricing/catalog/items',201,json={'category_id':child['id'],'name':'TEST Installation','unit':'Fixed','pricing_mode':'fixed','unit_price':'100','default_quantity':'1'})
        created_items.add(fixed['id'])
        assert call(b,'POST',f"/pricing/catalog/items/{fixed['id']}/quote",json={'quantity':'9'})['total_price'] == '100.00'
        archived = call(a,'PUT',f"/pricing/catalog/categories/{grandchild['id']}",json=cat_body(grandchild,archived=True))
        call(b,'POST',f"/pricing/catalog/items/{entry['id']}/quote",409,json={'quantity':'4'})
        call(b,'POST','/pricing/catalog/items',409,json={'category_id':grandchild['id'],'name':'Invalid hidden item','unit_price':'1'})
        restored = call(b,'PUT',f"/pricing/catalog/categories/{grandchild['id']}",json=cat_body(archived,archived=False))
        assert call(a,'POST',f"/pricing/catalog/items/{entry['id']}/quote",json={'quantity':'4'})['total_price'] == '61.00'
        call(a,'POST','/pricing/catalog/categories',422,json={'name':prefix+' nested','parent_id':parent['id']})
        call(a,'DELETE',f"/pricing/catalog/items/{edited['id']}?expected_version={edited['version']}",409)
        archived_item=call(b,'PUT',f"/pricing/catalog/items/{edited['id']}",json=item_body(edited,archived=True))
        call(a,'DELETE',f"/pricing/catalog/items/{edited['id']}?expected_version={edited['version']}",409)
        call(a,'DELETE',f"/pricing/catalog/items/{edited['id']}?expected_version={archived_item['version']}",204)
        call(b,'POST',f"/pricing/catalog/items/{edited['id']}/quote",404,json={'quantity':'1'})
        config=call(a,'GET','/pricing/config')['config']
        for key in ['rustic','bronze','clear']:
            quote=call(b,'POST','/pricing/calc/mirror',json={'square_footage':10,'mirror_type':key})
            assert quote['total']==10*config['mirror']['types'][key]['rate']+config['mirror']['minimum']
            assert quote['line_items'][0]['name']==config['mirror']['types'][key]['label']
        shelf=call(a,'POST','/pricing/calc/cabinet',json={'linear_footage':2,'cabinet_type':'shelving_unit'})
        assert shelf['total']==2*config['cabinet']['types']['shelving_unit']['base_rate']
        print(json.dumps({'checks':checks,'cross_user_persistence':True,'flat_categories_only':True,'archive_restore_delete':True,
                          'mirror_types_and_shelving':True,'legacy_rates_unchanged':call(a,'GET','/pricing/config')['revision']==before}))
    finally:
        # Preserve recoverability. Never modify pre-existing or staff-created entries.
        catalog = call(a,'GET','/pricing/catalog')
        for item in catalog['items']:
            if item['id'] in created_items:
                archived=call(a,'PUT',f"/pricing/catalog/items/{item['id']}",json=item_body(item,archived=True))
                call(a,'DELETE',f"/pricing/catalog/items/{item['id']}?expected_version={archived['version']}",204)
        for category in reversed(catalog['categories']):
            if category['id'] in created_categories:
                archived=call(a,'PUT',f"/pricing/catalog/categories/{category['id']}",json=cat_body(category,archived=True))
                call(a,'DELETE',f"/pricing/catalog/categories/{category['id']}?expected_version={archived['version']}",204)
        for client in clients: client.close()
        print('Only newly created TEST entries were archived and deleted; existing catalogue data was not edited.')


if __name__ == '__main__':
    main()
