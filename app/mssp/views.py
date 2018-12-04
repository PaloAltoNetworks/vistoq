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
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import TemplateView, RedirectView
from django.views.generic.edit import FormView

from mssp.forms import SimpleDemoForm
from mssp.lib import pan_utils
from mssp.lib import salt_utils
from mssp.lib import snippet_utils

from pan_cnc.views import CNCBaseFormView


class MSSPBaseAuth(LoginRequiredMixin):
    login_url = '/login'
    base_html = 'mssp/base.html'


class MSSPView(MSSPBaseAuth, TemplateView):
    template_name = "mssp/index.html"


class MSSPBaseFormView(FormView):
    overrides = {}

    @staticmethod
    def generate_dynamic_form(service):
        dynamic_form = forms.Form()
        for variable in service['variables']:
            print('Adding field %s' % variable['name'])
            field_name = variable['name']
            type_hint = variable['type_hint']
            description = variable['description']
            default = variable['default']
            # FIXME - set form field type based on type_hint
            dynamic_form.fields[field_name] = forms.CharField(label=description, initial=default)

        return dynamic_form


class ConfigureServiceView(MSSPBaseAuth, MSSPBaseFormView):
    """
    /mssp/configure

    This will instantiate the SimpleDemoForm from forms.py

    Allows the user to choose which snippet to load

    """
    template_name = 'mssp/simple_demo.html'
    form_class = forms.Form
    success_url = '/'

    def get_context_data(self, **kwargs):
        """
        Override get_context_data so we can modify the SimpleDemoForm as necessary.
        We want to dynamically add all the snippets in the snippets dir as choice fields on the form
        :param kwargs:
        :return:
        """
        form = self.get_form()

        # load all snippets with a type of 'service'
        services = snippet_utils.load_snippets_of_type('service')

        # we need to construct a new ChoiceField with the following basic format
        # service_tier = forms.ChoiceField(choices=(('gold', 'Gold'), ('silver', 'Silver'), ('bronze', 'Bronze')))
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
        form.fields['customer_name'] = forms.CharField(label='Customer Name', max_length=100)
        form.fields['service_tier'] = new_choices_field

        form.fields['platform_sizing'] = forms.ChoiceField(choices=(('small', 'Small'), ('medium', 'Medium'), ('large', 'Large')))
        form.fields['service_term'] = forms.ChoiceField(choices=(('3', '3 Year'), ('2', '2 Year'), ('1', '1 Year')))

        # save to kwargs and call parent for additional processing
        kwargs['form'] = form
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        """
        Called when the simple demo form is submitted
        :param form: SimpleDemoForm
        :return: rendered html response
        """
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        service_name = self.request.POST['service_tier']
        customer_name = self.request.POST['customer_name']
        service_term = self.request.POST['service_term']
        service = snippet_utils.load_snippet_with_name(service_name)
        print(service)
        dynamic_form = self.generate_dynamic_form(service)
        context = self.get_context_data()
        context['customer_name'] = customer_name
        context['service_term'] = service_term
        context['service'] = service
        context['form'] = dynamic_form
        return render(self.request, 'mssp/configure_service.html', context=context)


class ProvisionServiceView(MSSPBaseAuth, FormView):
    """
    Provision Service View - This view uses the Base Auth and Form View
    The posted view is actually a dynamically generated form so the forms.Form will actually be blank
    use form_valid as it will always be true in this case.
    """
    template_name = 'mssp/simple_demo.html'
    form_class = forms.Form
    success_url = '/mssp/services'

    def form_valid(self, form):
        """
        form_valid is always called on a blank / new form, so this is essentially going to get called on every POST
        self.request.POST should contain all the variables defined in the service identified by the hidden field
        'service_id'
        :param form: blank form data from request
        :return: render of a success template after service is provisioned
        """
        service_name = self.request.POST.get('service_id', '')
        customer_name = self.request.POST.get('customer_name', '')

        if service_name == '':
            # FIXME - add an ERROR page and message here
            print('No Service ID found!')
            return super().form_valid(form)

        service = snippet_utils.load_snippet_with_name(service_name)
        jinja_context = dict()

        jinja_context['customer_name'] = customer_name
        jinja_context['service_tier'] = service_name

        for v in service['variables']:
            if self.request.POST.get(v['name']):
                jinja_context[v['name']] = self.request.POST.get(v['name'])
            else:
                # FIXME - add an ERROR page and message here
                print('Required Variable not found on request!')
                return super().form_valid(form)

        # we now have a jinja context that contains all our variables and the user supplied inputs
        # FIXME - add pan.xapi stuff here to handle this stuff!
        print(jinja_context)

        # check if we need to ensure a baseline exists before hand
        if 'extends' in service and service['extends'] is not None:
            # prego (it's in there)
            baseline = service['extends']
            baseline_service = snippet_utils.load_snippet_with_name(baseline)
            # FIX for https://github.com/nembery/vistoq2/issues/5
            if 'variables' in baseline_service and type(baseline_service['variables']) is list:
                for v in baseline_service['variables']:
                    # FIXME - Should include a way show this in UI so we have POSTED values available
                    if 'default' in v:
                        # Do not overwrite values if they've arrived from the user via the Form
                        if v['name'] not in jinja_context:
                            print('Setting default from baseline on context for %s' % v['name'])
                            jinja_context[v['name']] = v['default']

            if baseline_service is not None:
                # check the panorama config to see if it's there or not
                if not pan_utils.validate_snippet_present(baseline_service, jinja_context):
                    # no prego (it's not in there)
                    print('Pushing configuration dependency: %s' % baseline_service['name'])
                    # make it prego
                    pan_utils.push_service(baseline_service, jinja_context)

        if not pan_utils.validate_snippet_present(service, jinja_context):
            print('Pushing new service: %s' % service['name'])
            pan_utils.push_service(service, jinja_context)
        else:
            print('This service was already configured on the server')

        return super().form_valid(form)


class ViewServicesView(MSSPBaseAuth, TemplateView):
    template_name = "mssp/service_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_list = pan_utils.get_device_groups_from_panorama()
        context['service_list'] = service_list
        return context


class ViewMinionsView(MSSPBaseAuth, TemplateView):
    template_name = "mssp/minion_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        salt_util = salt_utils.SaltUtil()
        minion_list = salt_util.get_minion_list()
        context['minion_list'] = minion_list
        return context


class MSSPBaseDynamicFormView(MSSPBaseFormView):
    form_class = forms.Form
    template_name = 'mssp/dynamic_form.html'
    success_url = '/mssp/results'
    snippet = ''
    header = 'Vistoq MSSP'
    title = 'Deploy'
    action = '/mssp/deploy'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = snippet_utils.load_snippet_with_name(self.snippet)
        form = self.generate_dynamic_form(service)
        context['form'] = form
        context['header'] = self.header
        return context


class DeployServiceView(MSSPBaseAuth, MSSPBaseDynamicFormView):
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
        # service_tier = forms.ChoiceField(choices=(('gold', 'Gold'), ('silver', 'Silver'), ('bronze', 'Bronze')))
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
        service = snippet_utils.load_snippet_with_name('provision_firewall')

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


class ViewDeployedVmsView(MSSPBaseAuth, MSSPBaseDynamicFormView):
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
        # service_tier = forms.ChoiceField(choices=(('gold', 'Gold'), ('silver', 'Silver'), ('bronze', 'Bronze')))
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
        service = snippet_utils.load_snippet_with_name(self.snippet)

        for v in service['variables']:
            if self.request.POST.get(v['name']):
                jinja_context[v['name']] = self.request.POST.get(v['name'])

        minion = self.request.POST.get('minion')
        salt_util = salt_utils.SaltUtil()
        res = salt_util.deploy_service(service, jinja_context)
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
        service = snippet_utils.load_snippet_with_name('delete_single_vm')
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


class TestCNCView(MSSPBaseAuth, CNCBaseFormView):
    snippet = 'silver-new'
    header = 'Configure Gold Service'
    title = 'This is a title'
    app_dir = 'mssp'

    def form_valid(self, form):
        results = dict()
        if 'variables' in self.service:
            for v in self.service['variables']:
                results[v['name']] = self.request.POST[v['name']]

        context = dict()
        context['results'] = results
        return render(self.request, 'mssp/results.html', context=context)