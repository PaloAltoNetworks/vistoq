# Copyright (c) 2018, Palo Alto Networks
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import json
import os
from pathlib import Path

import requests
from django.conf import settings
from jinja2 import Environment, BaseLoader
from requests.exceptions import ConnectionError


class SaltUtil():
    username = "saltuser"
    password = "saltuser"
    base_url = "http://provisioner:9000"
    login_url = '/login'
    auth_token = ''

    def __get_salt_auth_token(self):

        try:
            print('Here we go')
            # FIXME - check timeout here
            if self.auth_token != '':
                print('we have an auth token already')
                return True
            else:
                print('No auth token found!')

            _auth_json = """
               {
                "username" : "%s",
                "password" : "%s",
                "eauth": "pam"
                }
                """ % (self.username, self.password)
            print(_auth_json)
            aj = json.loads(_auth_json)
            headers = {"Content-Type": "application/json"}

            url = self.base_url + self.login_url
            print('Using url: %s' % url)
            res = requests.post(url, json=aj, headers=headers)
            print(res)
            if res.status_code == 200:
                json_results = res.json()
                if 'return' in json_results:
                    self._auth_token = json_results['return'][0]['token']
                    print(self._auth_token)
                    return True
                else:
                    return False

            else:
                print(res.text)
                return False

        except ConnectionError as ce:
            print(ce)
            return False
        except Exception as e:
            print(e)
            return False

    def get_minion_list(self):

        print('HERE WE GO')
        minion_list = list()
        if not self.__get_salt_auth_token():
            print('Could not connect to provisioner')
            return minion_list

        url = self.base_url + '/minions'
        headers = {"X-Auth-Token": self._auth_token}
        res = requests.get(url, headers=headers)
        print(res)
        print(res.text)
        minion_list_json = res.json()
        print(minion_list_json)

        if res.status_code != 200:
            print('Invalid return code')
            return minion_list

        if 'return' not in minion_list_json:
            print('Invalid return data')
            return minion_list

        for minion in minion_list_json['return']:
            # return data is return[0][some_name:some_data]

            # FIXME - will there ever be more than 1 key returned here?
            minion_name = list(minion.keys())[0]
            minion_list.append(minion_name)

        return minion_list

    def deploy_service(self, service, context):
        if not self.__get_salt_auth_token():
            print('Could not connect to provisioner')
            return 'No good'

        snippets_dir = Path(os.path.join(settings.BASE_DIR, 'mssp', 'snippets'))

        try:
            for snippet in service['snippets']:
                template_name = snippet['file']

                template_full_path = os.path.join(snippets_dir, service['name'], template_name)
                with open(template_full_path, 'r') as template:
                    template_string = template.read()
                    template_template = Environment(loader=BaseLoader()).from_string(template_string)
                    payload = template_template.render(context)
                    print(payload)
                    url = self.base_url + '/'
                    headers = {"X-Auth-Token": self._auth_token}
                    payload_json = json.loads(payload)
                    try:
                        res = requests.post(url, json=payload_json, headers=headers)
                        print(res.status_code)
                        return res.text
                    except ConnectionError as ce:
                        print(ce)
                        return 'Error during deploy'

        except Exception as e:
            print(e)
            print('Caught an error deploying service')
