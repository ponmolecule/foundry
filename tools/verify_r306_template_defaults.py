"""Execute actual template route bodies without FastAPI/auth/network dependencies."""
import ast,json
from pathlib import Path
from foundry.v2.new_engagement import FUNDING_DEFAULT_KEYS
source=ast.parse(Path('app.py').read_text())
for name in ('v31_template','v2_template'):
 node=next(x for x in source.body if isinstance(x,ast.FunctionDef) and x.name==name)
 node.decorator_list=[]
 namespace={'Depends':lambda _:None,'gate':None,'JSONResponse':lambda value,**kw:value}
 exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),namespace)
 result=namespace[name]()
 for key in FUNDING_DEFAULT_KEYS:assert result['assumptions'][key]==0,(name,key)
 if isinstance(result['assumptions'].get('nie_detail'),dict):assert result['assumptions']['nie_detail']['fdic_bp_ann']==0
 print(name,'PASS')
