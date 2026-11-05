import unittest
from unittest.mock import patch, Mock
import requests
import baze_client


class BazeTests(unittest.TestCase):
    @patch('baze_client.settings', return_value=('test-secret', 'gemini-test'))
    @patch('baze_client.requests.request')
    def test_common_image_request(self, send, settings):
        send.return_value = Mock(status_code=200)
        send.return_value.json.return_value = {'choices':[{'message':{'content':'{"frets":[]}'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}
        contents=[{'role':'user','parts':[{'inline_data':{'mime_type':'image/jpeg','data':'abc'}}]}]
        result,usage=baze_client.call_baze_json(contents)
        self.assertEqual(result,{'frets':[]})
        self.assertEqual(usage['totalTokenCount'],15)
        args,kw=send.call_args
        self.assertEqual(args[1],baze_client.BASE_URL+'/chat/completions/')
        self.assertEqual(kw['json']['messages'][0]['content'][0]['image_url']['url'],'data:image/jpeg;base64,abc')
        self.assertEqual(kw['json']['model'],'gemini-test')
        self.assertEqual(kw['headers']['Authorization'],'Bearer test-secret')
        self.assertFalse(kw['allow_redirects'])
        self.assertNotIn('test-secret',args[1])

    @patch('baze_client.settings', return_value=('test-secret', 'gemini-test'))
    @patch('baze_client.requests.request')
    def test_errors_do_not_expose_key(self,send,settings):
        send.side_effect=requests.ConnectionError('test-secret')
        with self.assertRaises(RuntimeError) as caught:
            baze_client.request_json('GET','/models/')
        self.assertNotIn('test-secret',str(caught.exception))
        send.side_effect=None
        send.return_value=Mock(status_code=401)
        with self.assertRaisesRegex(RuntimeError,'401'):
            baze_client.request_json('GET','/models/')

    @patch('baze_client.settings', return_value=('test-secret', 'gemini-test'))
    @patch('baze_client.request_json')
    def test_truncated_response_rejected(self,request,settings):
        request.return_value={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
        with self.assertRaises(RuntimeError): baze_client.call_baze_json([])

    @patch('baze_client.ROOT')
    @patch.dict('os.environ',{'BAZE_API_KEY':'environment-key','BAZE_MODEL':'gemini-env'})
    def test_environment_precedence(self,root):
        root.__truediv__.return_value.exists.return_value=True
        root.__truediv__.return_value.read_text.return_value='BAZE_API_KEY="file-key"\nBAZE_MODEL=gemini-file\n'
        self.assertEqual(baze_client.settings(),('environment-key','gemini-env'))

    @patch('baze_client.request_json')
    def test_same_prompt_and_image_for_three_models(self, request):
        request.return_value={'choices':[{'finish_reason':'stop','message':{'content':'{}'}}], 'usage':{}}
        contents=[{'role':'user','parts':[{'text':'same prompt'},
            {'inline_data':{'mime_type':'image/jpeg','data':'abc'}}]},
            {'role':'model','parts':[{'text':'{"example":1}'}]}]
        payloads=[]
        for model in ['gemini-3.5-flash','gpt-6.1-sol','claude-sonnet-5-5']:
            baze_client.call_baze_json(contents,model=model)
            payloads.append(request.call_args.args[2])
        self.assertEqual(payloads[0]['messages'],payloads[1]['messages'])
        self.assertEqual(payloads[1]['messages'],payloads[2]['messages'])
        self.assertEqual(payloads[2]['messages'][1]['role'],'assistant')

    def test_explanatory_text_json(self):
        self.assertEqual(baze_client.parse_json_object('Explanation. {"bbox":[1,2,3,4]}'), {'bbox':[1,2,3,4]})
        self.assertEqual(baze_client.parse_json_object('Result: {"frets":[{"fret_num":0}]}'), {'frets':[{'fret_num':0}]})
        with self.assertRaises(ValueError):
            baze_client.parse_json_object('Result {} or {}')

    def test_metrics_and_failure_accounting(self):
        from compare_baze_models import metrics, summarize
        square=[[0,0],[100,0],[100,20],[0,20]]
        result=metrics(square,square)
        self.assertEqual(result['polygon_iou'],1)
        self.assertEqual(result['mean_error_px'],0)
        summary=summarize([
            dict(model='x',status='ok',metrics=result,calls=[{'usage':{'totalTokenCount':10}}]),
            dict(model='x',status='failed',calls=[{}])],['x'])['x']
        self.assertEqual(summary['mean_iou_including_failures'],.5)
        self.assertEqual(summary['calls_without_token_counts'],1)


if __name__=='__main__': unittest.main()
