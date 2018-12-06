import jinja2
import sys
from pathlib import Path
import os
import oyaml
from jinja2 import meta
import string

snippets_dir = Path(sys.argv[1])
snippet_name = os.path.basename(snippets_dir)

# get the jinja environment to use it's parse function
env = jinja2.Environment()
all_variables = list()

metadata = dict()
metadata['variables'] = list()
metadata['snippets'] = list()
metadata['name'] = snippet_name

# env.filters['sha512_hash'] = jinja2_filters.sha512_hash
services = list()
for d in snippets_dir.rglob('./*'):
    if os.path.isfile(d):
        try:
            with open(d, 'r') as sc:
                template = sc.read()
                snippet_file_name = os.path.basename(d)
                metadata['snippets'].append({'name': snippet_file_name, 'file': snippet_file_name})
                # parse returns an AST that can be send to the meta module
                ast = env.parse(template)
                # return a set of all variable defined in the template
                template_variables = meta.find_undeclared_variables(ast)
                all_variables.extend(template_variables)
        except IOError as ioe:
            print('Could not open snippet file in dir %s' % d)
            print(ioe)
            continue

print('This is all the vars I found!')
print(all_variables)
for v in all_variables:
    var_dict = dict()
    var_dict['name'] = v
    var_dict['description'] = string.capwords(v.replace('_', ' '))
    var_dict['default'] = v
    var_dict['type_hint'] = 'text'
    metadata['variables'].append(var_dict)

print(oyaml.dump(metadata, default_flow_style=False))

