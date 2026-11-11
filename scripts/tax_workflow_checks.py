"""Tax workflow checks run only inside the disposable local audit schema."""
from io import BytesIO
from decimal import Decimal,ROUND_HALF_UP
from hashlib import sha256
from pypdf import PdfReader
from openpyxl import load_workbook

async def check_tax(call, client, pre_id, final_id, tokens):
    for eid,mode in ((pre_id,'pre'),(final_id,'final')):
        path=f'/estimates/{eid}'
        original=(await call('GET',path)).json()
        untouched={k:original[k] for k in ('subtotal','final_total','markup_pct','discount_pct','line_items','zones')}
        before_xlsx=load_workbook(BytesIO((await call('GET',f'/pdf/{eid}/passport')).content))
        snapshot=(await call('GET',path+'/presentation-tax')).json()
        assert snapshot['options']['enabled'] is False
        client.headers['If-Match']=snapshot['revision']
        saved=(await call('PATCH',path+'/presentation-tax',json={'enabled':True,'rate':'7'})).json()
        assert saved['pdf_layout']['presentation_tax']['rate']=='7'
        await call('PATCH',path+'/presentation-tax',409,json={'enabled':False})
        client.headers['If-Match']=saved['revision']
        for body in ({},{'enabled':'true'},{'enabled':True,'rate':-1},{'enabled':True,'rate':'NaN'},{'enabled':True,'rate':'101'},{'enabled':True,'amount':'1.001'},{'enabled':True,'other':1}):
            await call('PATCH',path+'/presentation-tax',422,json=body)
        saved=(await call('GET',path,headers={'Authorization':'Bearer '+tokens[0]})).json()
        assert saved['pdf_layout']['presentation_tax']['enabled'] is True
        client.headers['If-Match']=saved['revision']
        saved=(await call('PATCH',path+'/presentation-options',json={'show_grand_total':True})).json()
        for brand,count in (('wallpanels',25),('verona',29)):
            client.headers['If-Match']=saved['revision']
            saved=(await call('PATCH',path+'/proposal-brand',json={'brand':brand})).json()
            for options in ({'enabled':True,'mode':'percent','rate':'7'},{'enabled':True,'mode':'amount','amount':'123.45'},{'enabled':False}):
                client.headers['If-Match']=saved['revision']
                saved=(await call('PATCH',path+'/presentation-tax',json=options)).json()
                assert {k:saved[k] for k in untouched}==untouched
                snapshot=(await call('GET',path+'/presentation-tax')).json()
                base=Decimal(snapshot['subtotal'])
                tax=((base*Decimal('0.07')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) if options.get('mode')=='percent' else Decimal('123.45')) if options['enabled'] else Decimal(0)
                assert Decimal(snapshot['tax'])==tax and Decimal(snapshot['grand_total'])==base+tax
                inline=await call('GET',f'/pdf/{eid}/{mode}-estimate')
                download=await call('GET',f'/pdf/{eid}/{mode}-estimate?download=true')
                assert sha256(inline.content).digest()==sha256(download.content).digest()
                pdf=PdfReader(BytesIO(inline.content));text=' '.join(' '.join(p.extract_text() for p in pdf.pages[:-count]).split())
                assert ('TAX' in text)==options['enabled']
                if options['enabled']:assert f'${base+tax:,.2f}' in text
        # Enabled tax must follow Sigma visibility, independently of calculations.
        client.headers['If-Match']=saved['revision']
        saved=(await call('PATCH',path+'/presentation-tax',json={'enabled':True,'rate':'7'})).json()
        client.headers['If-Match']=saved['revision']
        saved=(await call('PATCH',path+'/presentation-options',json={'show_grand_total':False})).json()
        pdf=PdfReader(BytesIO((await call('GET',f'/pdf/{eid}/{mode}-estimate')).content))
        assert 'TAX (7%)' not in ' '.join(p.extract_text() for p in pdf.pages)
        after_xlsx=load_workbook(BytesIO((await call('GET',f'/pdf/{eid}/passport')).content))
        assert before_xlsx.sheetnames==after_xlsx.sheetnames
        assert [[tuple(c.value for c in row) for row in w] for w in before_xlsx]==[[tuple(c.value for c in row) for row in w] for w in after_xlsx]
        if mode=='final':
            pre=(await call('GET',f'/estimates/{pre_id}/presentation-tax')).json()
            assert pre['options']=={'enabled':True,'mode':'percent','rate':'7','amount':'0'}
