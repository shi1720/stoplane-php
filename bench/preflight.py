"""Check the lab's local runtime prerequisites without collecting measurements."""
import json
from run import Stack

if __name__=='__main__':
    with Stack() as stack:
        for lane in ['shared','split']:
            body,_=stack.request(lane,{'action':'init'})
            assert len(json.loads(body)['csrf'])==64
        print(json.dumps({'ready':True,'versions':stack.versions},indent=2))
    print('Temporary services and state removed.')
