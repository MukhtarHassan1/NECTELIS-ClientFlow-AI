from copy import deepcopy

def test_bad_payload_rejection_is_audited_without_personal_data(client,sample):
    p=deepcopy(sample)
    p['lead']['service']=''
    response=client.post('/api/v1/leads',json=p)
    assert response.status_code==422
    state=client.get('/api/v1/state').json()
    assert state['stats']['rejections']==1
    assert state['stats']['contacts']==0
    assert 'body.lead.service' in state['rejections'][0]['reason']
    assert sample['lead']['email'] not in state['rejections'][0]['reason']
