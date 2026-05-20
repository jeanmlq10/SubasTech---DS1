import ast
p='backend/telegram_bot/views.py'
s=open(p,'r',encoding='utf-8').read()
try:
    tree=ast.parse(s,p)
except Exception as e:
    print('AST_PARSE_ERROR',e)
    raise
funcs=[n.name for n in tree.body if isinstance(n,ast.FunctionDef)]
print('HAS_HANDLE_TECH:', '_handle_technician_selection' in funcs)
print('CALL_SITE_OK:', 'return _handle_technician_selection(session, cleaned_text, state)' in s)
