"""Build sanitized, importable n8n workflow with readable decision branches.
The backend is the single source of truth; n8n is a visual intake/orchestration layer.
"""
import json
from pathlib import Path
nodes=[]; connections={}
def node(name,t,params,x,y,version=1):
    nodes.append({'parameters':params,'id':name.lower().replace(' ','-'),'name':name,'type':t,
                  'typeVersion':version,'position':[x,y]})
def link(src,dst,output=0):
    connections.setdefault(src,{'main':[]})
    arr=connections[src]['main']
    while len(arr)<=output:arr.append([])
    arr[output].append({'node':dst,'type':'main','index':0})
node('Receive Lead','n8n-nodes-base.webhook',{
    'httpMethod':'POST','path':'nectelis-clientflow-demo','responseMode':'responseNode','options':{}},200,320,2)
node('Forward to Validated API','n8n-nodes-base.httpRequest',{
    'method':'POST','url':'={{ $env.CLIENTFLOW_API_URL || "http://host.docker.internal:8000/api/v1/leads" }}',
    'sendBody':True,'specifyBody':'json','jsonBody':'={{ JSON.stringify($json.body) }}',
    'options':{'timeout':30000}, 'sendHeaders':True,
    'headerParameters':{'parameters':[{'name':'Content-Type','value':'application/json'},
           {'name':'X-Clientflow-Key','value':'={{ $env.CLIENTFLOW_WEBHOOK_API_KEY || "" }}'}]}},470,320,4.2)
node('Was Appointment Booked?','n8n-nodes-base.if',{
    'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict'},
                  'combinator':'and','conditions':[{'id':'status','leftValue':'={{ $json.status }}',
                 'rightValue':'booked','operator':{'type':'string','operation':'equals'}}]}},720,320,2.2)
node('Return Confirmed Booking','n8n-nodes-base.respondToWebhook',{
    'respondWith':'json','responseBody':'={{ JSON.stringify($json) }}',
    'options':{'responseCode':200}},1000,210,1.1)
node('Return Review / Failure Status','n8n-nodes-base.respondToWebhook',{
    'respondWith':'json','responseBody':'={{ JSON.stringify($json) }}',
    'options':{'responseCode':200}},1000,430,1.1)
# HTTP failure goes to explicit, safe error response (no raw provider bodies).
http_node = next(x for x in nodes if x['name']=='Forward to Validated API')
http_node['onError'] = 'continueErrorOutput'
node('Return Safe API Error','n8n-nodes-base.respondToWebhook',{
    'respondWith':'json','responseBody':'{"status":"integration_error","message":"Demo backend unavailable or request rejected"}',
    'options':{'responseCode':502}},760,535,1.1)
link('Receive Lead','Forward to Validated API')
link('Forward to Validated API','Was Appointment Booked?')
link('Forward to Validated API','Return Safe API Error',1)
link('Was Appointment Booked?','Return Confirmed Booking',0)
link('Was Appointment Booked?','Return Review / Failure Status',1)
wf={'name':'NECTELIS | ClientFlow AI | Lead Intake → Verified Processing → Booking / Review',
    'nodes':nodes,'connections':connections,'active':False,'settings':{'executionOrder':'v1'},
    'pinData':{},'tags':[]}
Path(__file__).with_name('ClientFlow_AI_Lead_Orchestration.json').write_text(json.dumps(wf,indent=2))
print('Created sanitized workflow')
