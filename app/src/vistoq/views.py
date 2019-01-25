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

from django import forms
from django.contrib import messages
from django.shortcuts import render, HttpResponseRedirect

from pan_cnc.lib import cnc_utils
from pan_cnc.lib import pan_utils
from pan_cnc.lib import snippet_utils
from pan_cnc.views import CNCBaseFormView, ProvisionSnippetView, ChooseSnippetView, CNCView
from vistoq.lib import salt_utils


class ViewServicesView(CNCView):
    template_name = "mssp/service_list.html"
    base_html = 'vistoq/base.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_list = pan_utils.get_device_groups_from_panorama()
        context['service_list'] = service_list
        return context


class ViewMinionsView(CNCView):
    template_name = "vistoq/minion_list.html"
    base_html = 'vistoq/base.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        salt_util = salt_utils.SaltUtil()
        minion_list = salt_util.get_minion_list()
        context['minion_list'] = minion_list
        return context


class DeployServiceView(CNCBaseFormView):
    # template_name = 'vistoq/deploy_service.html'
    snippet = 'provision_firewall'
    base_html = 'vistoq/base.html'
    app_dir = 'vistoq'

    def get_snippet(self):
        return self.snippet

    def get_context_data(self, **kwargs):
        """
        Override get_context_data so we can modify the context as necessary
        :param kwargs:
        :return:
        """
        print('Getting vm_auth_key')
        vm_auth_key = self.get_value_from_workflow('vm_auth_key', '')
        if vm_auth_key == '':
            vm_auth_key = pan_utils.get_vm_auth_key_from_panorama()
            vakl = vm_auth_key.split(' ')
            if len(vakl) > 2:
                vm_auth_key = vakl[3]

        print(vm_auth_key)
        panorama_ip = cnc_utils.get_config_value('PANORAMA_IP', '0.0.0.0')
        print(panorama_ip)
        self.save_value_to_workflow('vm_auth_key', vm_auth_key)
        self.save_value_to_workflow('panorama_ip', panorama_ip)

        # Ensure we capture FW_NAME in case that has been set previously (easy button case)
        fw_name = self.get_value_from_workflow('FW_NAME', '')
        if fw_name != '':
            self.save_value_to_workflow('vm_name', fw_name)

        context = super().get_context_data(**kwargs)
        form = context['form']

        # load all snippets with a type of 'service'
        salt_util = salt_utils.SaltUtil()
        minion_list = salt_util.get_minion_list()

        # we need to construct a new ChoiceField with the following basic format
        # snippet_name = forms.ChoiceField(choices=(('gold', 'Gold'), ('silver', 'Silver'), ('bronze', 'Bronze')))
        choices_list = list()
        # grab each service and construct a simple tuple with name and label, append to the list
        for minion in minion_list:
            minion_label = minion.split('.')[0]
            choice = (minion, minion_label)
            choices_list.append(choice)

        # let's sort the list by the label attribute (index 1 in the tuple)
        choices_list = sorted(choices_list, key=lambda k: k[1])
        # convert our list of tuples into a tuple itself
        choices_set = tuple(choices_list)
        # make our new field
        new_choices_field = forms.ChoiceField(choices=choices_set)
        # set it on the original form, overwriting the hardcoded GSB version
        form.fields['minion'] = new_choices_field
        # save to kwargs and call parent for additional processing
        context['form'] = form
        return context

    def form_valid(self, form):
        print('Here we go deploying %s' % self.app_dir)
        jinja_context = dict()
        service = snippet_utils.load_snippet_with_name('provision_firewall', self.app_dir)
        for v in service['variables']:
            if self.request.POST.get(v['name']):
                jinja_context[v['name']] = self.request.POST.get(v['name'])

        template = snippet_utils.render_snippet_template(service, self.app_dir, jinja_context)
        print(template)

        salt_util = salt_utils.SaltUtil()
        res = salt_util.deploy_template(template)
        print(res)
        context = dict()
        context['base_html'] = self.base_html
        context['title'] = 'Deploy Next Generation Firewall'
        context['header'] = 'Deployment Results'

        try:
            results_json = json.loads(res)
        except ValueError as ve:
            print('Could not load results from provisioner!')
            print(ve)
            context['results'] = 'Error deploying VM!'
            return render(self.request, 'pan_cnc/results.html', context=context)
        except TypeError as te:
            print('Could not load results from provisioner!')
            print(te)
            context['results'] = 'Error deploying VM!'
            return render(self.request, 'pan_cnc/results.html', context=context)

        if 'minion' not in jinja_context:
            context['results'] = 'Error deploying VM! No compute node found in response'
            return render(self.request, 'pan_cnc/results.html', context=context)

        minion = jinja_context['minion']
        if 'return' in results_json and minion in results_json['return'][0]:
            r = results_json['return'][0][minion]
            steps = r.keys()
            for step in steps:
                step_detail = r[step]
                if step_detail['result'] is not True:
                    context['results'] = 'Error deploying VM! Not all steps completed successfully!\n\n'
                    context['results'] += step_detail['comment']
                    return render(self.request, 'pan_cnc/results.html', context=context)

        context['results'] = 'VM Deployed Successfully on CPE: %s' % minion
        return render(self.request, 'pan_cnc/results.html', context=context)


class ViewDeployedVmsView(CNCBaseFormView):
    """
    Show all the VMs currently deployed on the compute node

    GET will show the dynamic form based on the 'show_deployed_vms_on_node' snippet

    POST will load the snippet and execute it against
    """
    snippet = 'show_deployed_vms_on_node'
    header = 'Vistoq MSSP'
    title = 'Show Deployed VMs on Node'
    action = '/vistoq/vms'
    base_html = 'vistoq/base.html'
    app_dir = 'vistoq'

    def get_snippet(self):
        return self.snippet

    def get_context_data(self, **kwargs):
        """
        Override get_context_data so we can modify the SimpleDemoForm as necessary.
        We want to dynamically add all the snippets in the snippets dir as choice fields on the form
        :param kwargs:
        :return:
        """

        context = super().get_context_data(**kwargs)
        form = context['form']

        # load all snippets with a type of 'service'
        salt_util = salt_utils.SaltUtil()
        minion_list = salt_util.get_minion_list()

        # we need to construct a new ChoiceField with the following basic format
        # snippet_name = forms.ChoiceField(choices=(('gold', 'Gold'), ('silver', 'Silver'), ('bronze', 'Bronze')))
        choices_list = list()
        # grab each service and construct a simple tuple with name and label, append to the list
        for minion in minion_list:
            minion_label = minion.split('.')[0]
            choice = (minion, minion_label)
            choices_list.append(choice)

        # let's sort the list by the label attribute (index 1 in the tuple)
        choices_list = sorted(choices_list, key=lambda k: k[1])
        # convert our list of tuples into a tuple itself
        choices_set = tuple(choices_list)
        # make our new field
        new_choices_field = forms.ChoiceField(choices=choices_set)
        # set it on the original form, overwriting the hardcoded GSB version
        form.fields['minion'] = new_choices_field
        # save to kwargs and call parent for additional processing
        context['form'] = form
        return context

    def form_valid(self, form):
        print('Here we go deploying')
        minion = self.get_value_from_workflow('minion', '')
        salt_util = salt_utils.SaltUtil()

        template = snippet_utils.render_snippet_template(self.service, self.app_dir, self.get_workflow())

        res = salt_util.deploy_template(template)
        context = dict()
        context['base_html'] = self.base_html

        try:
            if res is None:
                context['results'] = 'Could not get deployed VM list, no valid return from CPE'
                return render(self.request, 'pan_cnc/results.html', context=context)

            response_obj = json.loads(res)
            # {"return": [{"compute-01.c.vistoq-demo.internal": {"shoaf1": "shutdown", "stuart1": "shutdown"}}]}
            fm = response_obj['return'][0]
            vms = list()
            if minion in fm:
                minion_dict = response_obj['return'][0][minion]
                for m in minion_dict:
                    vm_detail = dict()
                    vm_detail['hostname'] = m
                    vm_detail['status'] = minion_dict[m]
                    vms.append(vm_detail)

                context['vms'] = vms
                context['minion'] = minion
                return render(self.request, 'vistoq/deployed_vms.html', context=context)
            else:
                context['results'] = response_obj['return'][0]
                return render(self.request, 'pan_cnc/results.html', context=context)
        except ValueError as ve:
            print('Could not parse json')
            print(ve)
            context['results'] = {'Error': 'Could not get deployed VMs list!'}
            return render(self.request, 'pan_cnc/results.html', context=context)


class DeleteVMView(CNCView):
    template_name = 'pan_cnc/results.html'
    base_html = 'vistoq/base.html'
    app_dir = 'vistoq'

    def get_context_data(self, **kwargs):
        hostname = self.kwargs['hostname']
        minion = self.kwargs['minion']

        service = snippet_utils.load_snippet_with_name('delete_single_vm', self.app_dir)
        jinja_context = dict()
        for v in service['variables']:
            if kwargs.get(v['name']):
                jinja_context[v['name']] = kwargs.get(v['name'])

        template = snippet_utils.render_snippet_template(service, self.app_dir, jinja_context)
        salt_util = salt_utils.SaltUtil()
        res = salt_util.deploy_template(template)
        print(res)
        print('deleting hostname %s' % hostname)
        context = dict()
        context['base_html'] = self.base_html
        context['results'] = res

        return context


class GPCSView(CNCBaseFormView):
    """
    /vistoq/configure

    This will instantiate the SimpleDemoForm from forms.py

    Allows the user to choose which snippet to load

    """
    snippet = 'cnc-conf-gpcs'
    header = 'Provision Service: GPCS'
    title = 'Configure Service Sales information: GPCS'
    app_dir = 'vistoq'

    def get_context_data(self, **kwargs):
        """
        Override get_context_data so we can modify the SimpleDemoForm as necessary.
        We want to dynamically add all the snippets in the snippets dir as choice fields on the form
        :param kwargs:
        :return:
        """

        context = super().get_context_data(**kwargs)

        form = context['form']
        # load all snippets with a type of 'service'
        services = snippet_utils.load_snippets_of_type('gpcs')

        # we need to construct a new ChoiceField with the following basic format
        # snippet_name = forms.ChoiceField(choices=(('gold', 'Gold'), ('silver', 'Silver'), ('bronze', 'Bronze')))
        choices_list = list()
        # grab each service and construct a simple tuple with name and label, append to the list
        for service in services:
            choice = (service['name'], service['label'])
            choices_list.append(choice)

        # let's sort the list by the label attribute (index 1 in the tuple)
        choices_list = sorted(choices_list, key=lambda k: k[1])
        # convert our list of tuples into a tuple itself
        choices_set = tuple(choices_list)
        # make our new field
        new_choices_field = forms.ChoiceField(choices=choices_set)
        # set it on the original form, overwriting the hardcoded GSB version

        form.fields['snippet_name'] = new_choices_field

        context['form'] = form
        return context

    def form_valid(self, form):
        """
        Called when the simple demo form is submitted
        :param form: SimpleDemoForm
        :return: rendered html response
        """
        return HttpResponseRedirect('provision')


class GsbProvisionView(ProvisionSnippetView):
    base_html = 'vistoq/base.html'

    def generate_dynamic_form(self):
        simple_service = self.get_value_from_workflow('simple_service', '')
        print('simple service is ' + simple_service)
        if simple_service == 'on':
            print('only showing device name field')
            self.fields_to_render += ['FW_NAME']

        # save local workflow data to jinja context for template render
        self.save_workflow_to_session()

        return super().generate_dynamic_form()


class GsbWorkflow02(ProvisionSnippetView):
    base_html = 'vistoq/base.html'

    def create_sku(self):
        # decoder ring to map menu values to SKU elements
        sku_tier = {'gold': 'BND2', 'silver': 'BND1', 'bronze': 'BASIC'}
        sku_size = {'small': 'VM-50', 'medium': 'VM-300', 'large': 'VM-500'}
        sku_term = {'M': 'MU', '1': 'YU', '3': '3YU'}

        user_tier = self.get_value_from_workflow('snippet_name', '').split('_')[0]
        user_size = self.get_value_from_workflow('service_size', '')
        user_term = self.get_value_from_workflow('service_term', '')

        sku = 'PAN-{0}-SP-BKLN-{1}-{2}'.format(sku_size[user_size],
                                               sku_tier[user_tier],
                                               sku_term[user_term])

        self.save_value_to_workflow('sku', sku)
        print('sku is {0}'.format(sku))

    def generate_dynamic_form(self):
        # get customer name and use for fw name
        customer_name = self.get_value_from_workflow('customer_name', '')
        self.save_value_to_workflow('FW_NAME', customer_name)

        # only show the FW_NAME field to validate name used
        self.fields_to_render = ['FW_NAME']

        # create a sku value based on form input data
        self.create_sku()
        # save local workflow data to jinja context for template render
        self.save_workflow_to_session()

        return super().generate_dynamic_form()

    def form_valid(self, form):
        """
        Called when the simple demo form is submitted
        :param form: SimpleDemoForm
        :return: rendered html response
        """

        # get FW_NAME value from form submit
        fw_name = self.get_value_from_workflow('FW_NAME', '')

        # set stack and device-group names to fw_name
        self.save_value_to_workflow('STACK', fw_name)
        self.save_value_to_workflow('DEVICE_GROUP', fw_name)
        # Force Gold and Silver to NOT include EDL rules
        self.save_value_to_workflow('INCLUDE_PAN_EDL', 'False')

        print('set device-group and stack to firewall name')

        return super().form_valid(form)


class VistoqChooseSnippetView(ChooseSnippetView):
    base_html = 'vistoq/base.html'


class VistoqRedirectView(CNCView):
    template_name = 'vistoq/redirect.html'

    def get_context_data(self, **kwargs):
        context = dict()
        panorama_ip = cnc_utils.get_config_value('PANORAMA_IP', '0.0.0.0')
        if panorama_ip == '0.0.0.0':
            panorama_ip = self.get_value_from_workflow('TARGET_IP', '0.0.0.0')
            if panorama_ip == '0.0.0.0':
                print('Could not load panorama ip')
                messages.add_message(self.request, messages.ERROR, 'Could not locate Panorama Configuration')
                context['redirect_link'] = '/'
                return context

            context['redirect_link'] = f'https://{panorama_ip}'
        else:
            context['redirect_link'] = f'https://{panorama_ip}'

        return context
