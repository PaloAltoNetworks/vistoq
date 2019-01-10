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
from django.shortcuts import render, HttpResponseRedirect
from django.views.generic import TemplateView

from pan_cnc.lib import pan_utils
from pan_cnc.lib import snippet_utils
from pan_cnc.views import CNCBaseFormView, CNCBaseAuth, ProvisionSnippetView, ChooseSnippetView
from vistoq.lib import salt_utils


class ViewServicesView(CNCBaseAuth, TemplateView):
    template_name = "mssp/service_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_list = pan_utils.get_device_groups_from_panorama()
        context['service_list'] = service_list
        return context


class ViewMinionsView(CNCBaseAuth, TemplateView):
    template_name = "mssp/minion_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        salt_util = salt_utils.SaltUtil()
        minion_list = salt_util.get_minion_list()
        context['minion_list'] = minion_list
        return context


class DeployServiceView(CNCBaseAuth, CNCBaseFormView):
    template_name = 'mssp/deploy_service.html'
    snippet = 'provision_firewall'

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
        jinja_context = dict()
        service = snippet_utils.load_snippet_with_name('provision_firewall', self.app_dir)

        for v in service['variables']:
            if self.request.POST.get(v['name']):
                jinja_context[v['name']] = self.request.POST.get(v['name'])

        salt_util = salt_utils.SaltUtil()
        res = salt_util.deploy_service(service, jinja_context)
        context = dict()
        try:
            results_json = json.loads(res)
        except ValueError as ve:
            print('Could not load results from provisioner!')
            print(ve)
            context['results'] = 'Error deploying VM!'
            return render(self.request, 'mssp/results.html', context=context)

        if 'minion' not in jinja_context:
            context['results'] = 'Error deploying VM! No compute node found in response'
            return render(self.request, 'mssp/results.html', context=context)

        minion = jinja_context['minion']
        if 'return' in results_json and minion in results_json['return'][0]:
            r = results_json['return'][0][minion]
            steps = r.keys()
            for step in steps:
                step_detail = r[step]
                if step_detail['result'] is not True:
                    context['results'] = 'Error deploying VM! Not all steps completed successfully!\n\n'
                    context['results'] += step_detail['comment']
                    return render(self.request, 'mssp/results.html', context=context)

        context['results'] = 'VM Deployed Successfully on CPE: %s' % minion
        return render(self.request, 'mssp/results.html', context=context)


class ViewDeployedVmsView(CNCBaseAuth, CNCBaseFormView):
    """
    Show all the VMs currently deployed on the compute node

    GET will show the dynamic form based on the 'show_deployed_vms_on_node' snippet

    POST will load the snippet and execute it against
    """
    snippet = 'show_deployed_vms_on_node'
    header = 'Vistoq MSSP'
    title = 'Show Deployed VMs on Node'
    action = '/mssp/vms'

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
        res = salt_util.deploy_service(self.service, self.get_workflow())
        context = dict()

        try:
            if res is None:
                context['results'] = 'Could not get deployed VM list, no valid return from CPE'
                return render(self.request, 'mssp/results.html', context=context)

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
                return render(self.request, 'mssp/deployed_vms.html', context=context)
            else:
                context['results'] = response_obj['return'][0]
                return render(self.request, 'mssp/results.html', context=context)
        except ValueError as ve:
            print('Could not parse json')
            print(ve)
            context['results'] = {'Error': 'Could not get deployed VMs list!'}
            return render(self.request, 'mssp/results.html', context=context)


class DeleteVMView(TemplateView):
    template_name = 'mssp/results.html'

    def get_context_data(self, **kwargs):
        hostname = self.kwargs['hostname']
        minion = self.kwargs['minion']
        service = snippet_utils.load_snippet_with_name('delete_single_vm', self.app_dir)
        jinja_context = dict()
        for v in service['variables']:
            if kwargs.get(v['name']):
                jinja_context[v['name']] = kwargs.get(v['name'])

        salt_util = salt_utils.SaltUtil()
        res = salt_util.deploy_service(service, jinja_context)
        print(res)
        print('deleting hostname %s' % hostname)
        context = dict()
        context['results'] = res

        return context


class GPCSView(CNCBaseAuth, CNCBaseFormView):
    """
    /mssp/configure

    This will instantiate the SimpleDemoForm from forms.py

    Allows the user to choose which snippet to load

    """
    snippet = 'cnc-conf-gpcs'
    header = 'Provision Service: GPCS'
    title = 'Configure Service Sales information: GPCS'
    app_dir = 'mssp'

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


class gsbProvisionView(ProvisionSnippetView):
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

class gsbWorkflow02(ProvisionSnippetView):
    base_html = 'vistoq/base.html'

    def generate_dynamic_form(self):

        self.fields_to_render = ['FW_NAME']

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

        print('set device-group and stack to firewall name')

        return super().form_valid(form)


class vistoqChooseSnippetView(ChooseSnippetView):
    base_html = 'vistoq/base.html'

