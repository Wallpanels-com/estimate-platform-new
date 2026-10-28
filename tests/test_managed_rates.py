from test_pricebook import unittest, HTTPException, DEFAULT_PRICING_CONFIG, calculate
from app.services.managed_rates import with_managed_rates,pricing_schema,validate_additions

class ManagedRates(unittest.TestCase):
    def test_mirror_types_split_installation_and_preserve_legacy(self):
        config=with_managed_rates(DEFAULT_PRICING_CONFIG)
        for key,rate in [('rustic',100),('bronze',100),('clear',80)]:
            result=calculate('mirror',config,square_footage=10,mirror_type=key)
            self.assertEqual(result['total'],10*rate+1000)
            self.assertEqual(result['line_items'][0]['unit_price'],rate)
            self.assertEqual(result['line_items'][1]['total_price'],1000)
            self.assertEqual(result['line_items'][0]['name'],config['mirror']['types'][key]['label'])
        self.assertEqual(calculate('mirror',config,square_footage=20)['total'],2600)
        self.assertEqual(calculate('cabinet',config,linear_footage=2,cabinet_type='shelving_unit')['total'],1600)
        with self.assertRaises(HTTPException):calculate('mirror',config,square_footage=1,mirror_type='unknown')

    def test_custom_rates_work_in_existing_formulas(self):
        config=with_managed_rates(DEFAULT_PRICING_CONFIG)
        config['wall']['base_rates']['custom']=73
        config['wall']['addons_sf']['extra']={'label':'Custom finish','price':7,'describable':False}
        config['_rate_labels']={'wall.base_rates.custom':{'label':'Selected base','label_ru':'Выбранная ставка'}}
        self.assertEqual(calculate('wall',config,square_footage=10,base_rate_key='custom',addons_sf=['extra'])['total'],800)
        self.assertEqual(calculate('wall',config,square_footage=10)['total'],600)
        schema=pricing_schema(config)
        self.assertEqual(schema['mirror']['types'][0]['rate'],100)
        self.assertEqual(schema['wall']['base_rates'][-1]['label'],'Selected base')
        validate_additions(config)
        config['mirror']['types']['bad']={'label':'Bad','rate':'string'}
        with self.assertRaises(HTTPException):validate_additions(config)
