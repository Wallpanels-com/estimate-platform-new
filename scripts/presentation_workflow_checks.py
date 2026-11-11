"""Saved display settings and matching inline/download exports; disposable audit only."""
from hashlib import sha256
from io import BytesIO
from pypdf import PdfReader

async def check_presentation_options(call, client, pre_id, final_id, tokens):
    for eid in (pre_id, final_id):
        path = f'/estimates/{eid}'
        original = (await call('GET', path)).json()
        numeric = {key: original[key] for key in ('subtotal', 'final_total', 'markup_pct', 'discount_pct', 'line_items', 'zones')}
        client.headers['If-Match'] = original['revision']
        saved = (await call('PATCH', path+'/presentation-options', json={'show_calculations':False})).json()
        assert saved['pdf_layout']['presentation_options'] == {'show_grand_total':True,'show_calculations':False}
        await call('PATCH', path+'/presentation-options',409,json={'show_grand_total':False})
        client.headers['If-Match'] = saved['revision']
        for invalid in ({}, {'show_grand_total':'false'}, {'other':True}):
            await call('PATCH',path+'/presentation-options',422,json=invalid)
        # Another employee sees persisted preferences with a different token.
        observed = (await call('GET',path,headers={'Authorization':'Bearer '+tokens[0]})).json()
        assert observed['pdf_layout']['presentation_options']['show_calculations'] is False
        mode = 'pre' if eid == pre_id else 'final'
        for brand, count in (('wallpanels',25), ('verona',29)):
            client.headers['If-Match'] = observed['revision']
            observed = (await call('PATCH',path+'/proposal-brand',json={'brand':brand})).json()
            for total in (True,False):
                for calculations in (True,False):
                    client.headers['If-Match'] = observed['revision']
                    observed = (await call('PATCH',path+'/presentation-options',json={'show_grand_total':total,'show_calculations':calculations})).json()
                    assert observed['pdf_layout']['proposal_brand'] == brand
                    assert {key:observed[key] for key in numeric} == numeric
                    inline = await call('GET',f'/pdf/{eid}/{mode}-estimate')
                    attachment = await call('GET',f'/pdf/{eid}/{mode}-estimate?download=true')
                    assert sha256(inline.content).digest() == sha256(attachment.content).digest(), 'Preview/download byte mismatch'
                    pdf = PdfReader(BytesIO(inline.content),strict=True)
                    assert pdf.metadata['/WallPanelsCompanySlidesCount'] == str(count)
                    text = ' '.join(' '.join(p.extract_text() for p in pdf.pages[:-count]).split())
                    assert ('GRAND TOTAL' in text if mode == 'final' else 'Current Calculation Basis' in text) == total
                    assert ('×' in text) == calculations, f'{mode} calculations must be generated from saved numeric fields'
        # Each branch keeps its own preferences; changing Final never resets Pre.
        if mode == 'final':
            other = (await call('GET',f'/estimates/{pre_id}')).json()
            assert other['pdf_layout']['presentation_options'] == {'show_grand_total':False,'show_calculations':False}
